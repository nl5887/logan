from requests.sessions import ChunkedEncodingError
import polars as pl
import pyarrow as pa
import json
import asyncio
from datetime import datetime, timedelta
from rivendel import Secrets
from dateutil.parser import isoparse
import re
import html2text
import httpx
import aiostream
from loguru import logger

from azure.identity import ClientSecretCredential
from msgraph.core import GraphClient, HTTPClientFactory


async def chunks(it, n):
    """Yield successive n-sized chunks from async iterator or aiostream."""
    chunk = []

    try:
        # Handle aiostream Stream objects
        if hasattr(it, "__aiter__"):
            async for item in it:
                chunk.append(item)

                if len(chunk) >= n:
                    yield chunk
                    chunk = []
        else:
            # Handle regular async iterators
            while True:
                item = await anext(it)
                chunk.append(item)

                if len(chunk) >= n:
                    yield chunk
                    chunk = []

    except StopAsyncIteration:
        pass

    if chunk:
        yield chunk


class GraphEnumClient:
    def __init__(self, credentials):
        self.credentials = credentials
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        self._token = None
        self._throttle_remaining = None  # Track remaining requests

    async def _get_auth_headers(self):
        """Get authorization headers with valid token"""
        if not self._token:
            # Get token from credentials
            token = await asyncio.get_event_loop().run_in_executor(
                None, self.credentials.get_token, "https://graph.microsoft.com/.default"
            )
            self._token = token.token

        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def _update_throttle_info(self, response):
        """Update throttle information from response headers"""
        # Track remaining requests from Graph API headers
        remaining = response.headers.get("X-RateLimit-Remaining")
        if not remaining:
            remaining = response.headers.get("x-ms-resource-unit-quota-remaining")

        if remaining:
            try:
                self._throttle_remaining = int(remaining)
            except (ValueError, TypeError):
                pass

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def get(self, url, params={}, limit=None):
        retry_count = 0
        max_retries = 5

        count = 0

        while url:
            try:
                headers = await self._get_auth_headers()

                # Log the full URL with params for debugging
                print(f"Graph API request: {url} with params: {params}")

                response = await self.client.get(url, headers=headers, params=params)

                # Update throttle info from response headers
                await self._update_throttle_info(response)

                if response.status_code == 429:  # Too Many Requests
                    retry_after = response.headers.get("Retry-After", "30")
                    delay = int(retry_after)

                    print(
                        f"Rate limited. Waiting for {delay} seconds before retrying..."
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code == 401:  # Unauthorized - token might be expired
                    print("Token expired, refreshing...")
                    self._token = None  # Reset token to force refresh
                    headers = await self._get_auth_headers()
                    response = await self.client.get(
                        url, headers=headers, params=params
                    )

                if response.status_code != 200:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get(
                            "message", "Unknown error"
                        )
                    except:
                        error_msg = f"HTTP {response.status_code}"
                    raise Exception(f"API error: {response.status_code} - {error_msg}")

                data = response.json()

                for v in data.get("value", []):
                    yield v
                    count += 1

                    if limit is not None and count >= limit:
                        return

                url = data.get("@odata.nextLink")
                logger.info(f"Graph API URL (nextLink): {url}")

                params = None

                retry_count = 0  # Reset retry count on successful request
            except httpx.TimeoutException:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"Max retries exceeded: Timeout")
                    raise

                wait_time = 2**retry_count
                logger.warning(
                    f"Timeout accessing {url}. Retrying in {wait_time} seconds..."
                )
                await asyncio.sleep(wait_time)

            except Exception as e:
                raise

                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"Max retries exceeded: {e}")
                    raise

                wait_time = 2**retry_count  # Exponential backoff
                logger.warning(
                    f"Error accessing {url}: {e}. Retrying in {wait_time} seconds..."
                )
                await asyncio.sleep(wait_time)


def parse_date(v):
    if v is None:
        return None
    if v == "0001-01-01T00:00:00Z":
        return None
    if v == "9999-12-31T23:59:59Z":
        return None

    dt = isoparse(v)
    return dt


def try_convert_value(value):
    """Try to convert a value to an appropriate type.

    Args:
        value: The value to convert

    Returns:
        The converted value, or the original value if no conversion is possible
    """
    if value is None:
        return None

    # If it's already a non-string type, return it as is
    if not isinstance(value, str):
        return value

    # Trim whitespace
    value = value.strip()

    # Empty string
    if value == "":
        return value

    # Try to convert to datetime
    try:
        return parse_date(value)
    except (ValueError, TypeError):
        pass

    # Try to convert to number
    try:
        # First try integer
        return int(value)
    except (ValueError, TypeError):
        pass

    try:
        # Then try float
        return float(value)
    except (ValueError, TypeError):
        pass

    # Try to convert to boolean
    if value.lower() in ["true", "false"]:
        return value.lower() == "true"
    elif value.lower() in ["yes", "no"]:
        return value.lower() == "yes"
    elif value.lower() in ["y", "n"]:
        return value.lower() == "y"
    elif value.lower() in ["1", "0"]:
        return value == "1"

    # Return the original value if no conversion is possible
    return value


def process_item_recursively(item):
    """Process an item recursively, converting values to appropriate types.

    Args:
        item: The item to process
        auto_convert: Whether to automatically convert values to appropriate types

    Returns:
        The processed item
    """
    if item is None:
        return None

    if isinstance(item, dict):
        result = {}
        for key, value in item.items():
            # Skip @odata type fields
            if key == "@odata.type" or key.endswith("@odata.context"):
                result[key] = value
                continue

            if isinstance(value, (dict, list)):
                result[key] = process_item_recursively(value)
            else:
                result[key] = try_convert_value(value)

        return result
    elif isinstance(item, list):
        return [process_item_recursively(i) for i in item]
    else:
        return try_convert_value(item)


class AzureGraphSchemaProvider:
    def __init__(self, params):
        from config import config

        self._tables = {}

        self.params = {**config, **params}

        logger.info("Configuring Azure Graph Schema provider", self.params)

        from urllib.parse import urlparse, urljoin

        credentials = self.params.get("secretId")
        if credentials is None:
            raise Exception("Secret not configured")

        u = urlparse(credentials)
        secret_path = u.path[1:]

        self.secret = json.loads(Secrets.get("brick-secrets", secret_path))
        if self.secret is None:
            raise Exception("Secret not found")

        logger.info("Done configuring Azure Graph Schema provider", self.params)

    def tables(self):
        # Return all available table names
        return list(self.params.get("tables", {}).keys())

    def table(self, name):
        # Return a table provider for the requested table
        if (table := self._tables.get(name)) is not None:
            return table

        table_config = self.params.get("tables", {}).get(name)
        if table_config is None:
            raise Exception(f"Table '{name}' doesn't exist")

        # Create the appropriate table provider based on custom_processing or endpoint
        class_name = table_config.get("class_name")

        if name == "emails":
            self._tables[name] = EmailTableProvider(name, self.secret, table_config)
        else:
            self._tables[name] = AzureGraphTableProvider(
                name, self.secret, table_config
            )

        return self._tables.get(name)


class BaseAzureTableProvider:
    def __init__(self, name, secret, config):
        self._name = name
        self._secret = secret
        self._config = config
        self._endpoint = config.get("endpoint")
        self._select = config.get("select")
        self._filter = config.get("filter")
        self._chunk_size = config.get("chunk_size", 100)
        self._schema = None
        # Always use auto_convert by default
        self._auto_convert = True

    async def scan(self):
        return Statistics(
            num_rows=None,
            is_exact=False,
            total_byte_size=None,
            column_statistics=ColumnStatistics(
                null_count=None,
                distinct_count=None,
                max_value=None,
                min_value=None,
            ),
        )


class AzureGraphTableProvider(BaseAzureTableProvider):
    def __init__(self, name, secret, config):
        super().__init__(name, secret, config)

        self._top = config.get("top")

        self._expand = config.get("expand")
        # Type conversion settings
        self._type_conversion = config.get("type_conversion", {})

        # Initialize Graph API client
        CLIENT_ID = secret.get("AZURE_CLIENT_ID")
        CLIENT_SECRET = secret.get("AZURE_CLIENT_SECRET")
        TENANT_ID = secret.get("AZURE_TENANT_ID")

        credentials = ClientSecretCredential(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
        self.client = GraphEnumClient(credentials)

    async def schema(self):
        mailbox = self._config.get("mailboxes")[0]

        (url, params) = self._build_url(mailbox, [], [], top=10)

        data = []
        try:
            async for item in self.client.get(url, params=params, limit=10):
                processed_item = process_item_recursively(item)

                for item in self.process_item(mailbox, processed_item):
                    data.append(item)

        except Exception as e:
            logger.error(f"Error fetching schema sample: {e}")
            return pa.schema([])

        rb = pa.RecordBatch.from_pylist(data)
        self._schema = rb.schema  # pa.Schema.from_pandas(df.to_pandas())

        return self._schema

    def _build_url(self, mailbox, filters=[], exprs=[], top=None, use_search=False):
        # Extract version from endpoint if present, otherwise default to v1.0
        endpoint = self._endpoint
        version = "v1.0"

        # Check if endpoint contains version information
        if endpoint.startswith("v1.0/") or endpoint.startswith("beta/"):
            parts = endpoint.split("/", 1)
            version = parts[0]
            endpoint = parts[1] if len(parts) > 1 else ""

        endpoint = endpoint.format(mailbox=mailbox)

        url = f"https://graph.microsoft.com/{version}/{endpoint}"

        params = {}

        if self._expand:
            params["$expand"] = self._expand

        if top:
            params["$top"] = top

        if self._select:
            params["$select"] = self._select

        import datafusion
        import rivendel

        # Get configuration
        table_config = self._config
        column_mappings = table_config.get("column_mappings", {})
        use_filter = table_config.get("use_filter", True)
        use_search_param = table_config.get("use_search", False) or use_search

        # Default mappings that work for most Graph API resources
        DEFAULT_COLUMN_MAPPING = {
            "id": "id",
            "subject": "subject",
            "body": "body",
            "receivedDateTime": "receivedDateTime",
            "sentDateTime": "sentDateTime",
            "createdDateTime": "createdDateTime",
            "lastModifiedDateTime": "lastModifiedDateTime",
        }

        # Merge default and configured mappings
        COLUMN_MAPPING = {**DEFAULT_COLUMN_MAPPING, **column_mappings}

        def validate_graph_field_path(field_path):
            """Validate and fix field paths for Graph API compatibility"""
            print(f"DEBUG: validate_graph_field_path input: '{field_path}'")

            # Get supported field paths from config
            supported_nested_fields = table_config.get("supported_nested_fields", [])
            array_fields = table_config.get("array_fields", [])

            # Check if this is a configured supported nested field
            if field_path in supported_nested_fields:
                print(
                    f"DEBUG: validate_graph_field_path returning configured nested field: '{field_path}'"
                )
                return field_path

            # Handle array field paths - keep them as-is for special processing
            elif field_path and (
                "[" in field_path
                or any(field_path.startswith(af) for af in array_fields)
            ):
                print(
                    f"DEBUG: validate_graph_field_path keeping array path: '{field_path}'"
                )
                return field_path

            print(f"DEBUG: validate_graph_field_path returning: '{field_path}'")
            return field_path

        def extract_datafusion_value(obj):
            """Extract actual value from DataFusion objects"""
            if obj is None:
                return None

            # Handle Literal objects (both rivendel and datafusion)
            if hasattr(obj, "value"):
                return obj.value

            # Return string representation as fallback
            return str(obj)

        def to_odata_filter(expr):
            """Convert datafusion/rivendel expression to OData filter syntax"""
            print(f"DEBUG: Processing expression: {expr} (type: {type(expr)})")

            # Check if this is a datafusion class
            type_name = str(type(expr))
            if "datafusion" in type_name:
                class_name = expr.__class__.__name__
                print(f"DEBUG: Datafusion class: {class_name}")

                if class_name == "Like":
                    return handle_like_expression(expr)
                elif isinstance(expr, rivendel.ScalarFunction):
                    if expr.name == "get_field":
                        return handle_get_field_function(expr)
                    elif expr.name == "array_element":
                        return handle_array_element_function(expr)
                elif isinstance(expr, rivendel.Column):
                    column_name = expr.name
                    return COLUMN_MAPPING.get(column_name, column_name)
                else:
                    print(f"DEBUG: Unhandled expression type: {type(expr)}")
                    # Fall through to remaining handling

            if isinstance(expr, rivendel.Alias):
                return to_odata_filter(expr.expr)
            elif isinstance(expr, rivendel.Column):
                # Map column name to Graph API field
                column_name = expr.name
                return COLUMN_MAPPING.get(column_name, column_name)
            elif isinstance(expr, rivendel.IndexedField):
                # Handle nested field access recursively like from['emailAddress']['address']
                print(f"DEBUG: IndexedField - expr: {expr.expr}, key: {expr.key}")

                # Recursively process the base expression
                base_field = to_odata_filter(expr.expr)
                key = expr.key

                # Handle Literal key (quoted strings)
                if isinstance(key, rivendel.Literal):
                    key = key.value
                    print(f"DEBUG: Key was Literal, extracted value: {key}")

                # Remove quotes from key if present
                if isinstance(key, str) and key.startswith("'") and key.endswith("'"):
                    key = key[1:-1]
                    print(f"DEBUG: Removed quotes from key: {key}")

                # Build path recursively - no hardcoded special cases needed
                result = f"{base_field}/{key}"
                print(f"DEBUG: IndexedField result: {result}")
                return result
            elif isinstance(expr, rivendel.Cast):
                return to_odata_filter(expr.expr)
            elif isinstance(expr, rivendel.ScalarFunction):
                if expr.name == "get_field":
                    args = expr.args
                    base = to_odata_filter(args[0])
                    field = args[1].value
                    # Remove quotes if present
                    if (
                        isinstance(field, str)
                        and field.startswith("'")
                        and field.endswith("'")
                    ):
                        field = field[1:-1]
                    return f"{base}/{field}"
                raise Exception(
                    f"Scalar function: {expr.name} not supported in OData filter."
                )
            elif isinstance(expr, rivendel.ScalarVariable):
                return str(expr)
            elif isinstance(expr, str):
                return f"'{expr}'"
            elif isinstance(expr, rivendel.IsNull):
                return f"{to_odata_filter(expr.expr)} eq null"
            elif isinstance(expr, rivendel.IsNotNull):
                return f"{to_odata_filter(expr.expr)} ne null"
            elif isinstance(expr, rivendel.InList):
                # OData doesn't have IN operator, convert to OR chain
                field = to_odata_filter(expr.expr)
                values = [to_odata_filter(item) for item in expr.list]
                or_conditions = [f"{field} eq {value}" for value in values]
                condition = "(" + " or ".join(or_conditions) + ")"
                return f"not ({condition})" if expr.negated else condition
            elif isinstance(expr, rivendel.Literal):
                if isinstance(expr.value, str):
                    return f"'{expr.value}'"
                elif isinstance(expr.value, bool):
                    return "true" if expr.value else "false"
                elif isinstance(expr.value, datetime):
                    return f"{expr.value.isoformat()}Z"
                else:
                    return str(expr.value)
            elif isinstance(expr, rivendel.BinaryExpr):
                left = to_odata_filter(expr.left)
                right = to_odata_filter(expr.right)

                if expr.operator.lower() == "and":
                    return f"({left}) and ({right})"
                elif expr.operator == "=":
                    return f"{left} eq {right}"
                elif expr.operator == "!=":
                    return f"{left} ne {right}"
                elif expr.operator == ">":
                    return f"{left} gt {right}"
                elif expr.operator == ">=":
                    return f"{left} ge {right}"
                elif expr.operator == "<":
                    return f"{left} lt {right}"
                elif expr.operator == "<=":
                    return f"{left} le {right}"
                elif expr.operator.lower() == "like" or expr.operator.lower() == "~*":
                    # Convert LIKE to OData contains/startswith/endswith
                    if isinstance(expr.right, rivendel.Literal) and isinstance(
                        expr.right.value, str
                    ):
                        pattern = expr.right.value
                        print(f"DEBUG: LIKE pattern: '{pattern}'")

                        # Handle single quotes in pattern
                        if pattern.startswith("'") and pattern.endswith("'"):
                            pattern = pattern[1:-1]
                            print(f"DEBUG: Removed outer quotes: '{pattern}'")

                        if pattern.startswith("%") and pattern.endswith("%"):
                            # %text% -> contains
                            search_term = pattern[1:-1]
                            result = f"contains({left}, '{search_term}')"
                        elif pattern.startswith("%"):
                            # %text -> endswith
                            search_term = pattern[1:]
                            result = f"endsWith({left}, '{search_term}')"
                        elif pattern.endswith("%"):
                            # text% -> startswith
                            search_term = pattern[:-1]
                            result = f"startsWith({left}, '{search_term}')"
                        else:
                            # Exact match
                            result = f"{left} eq '{pattern}'"

                        print(f"DEBUG: LIKE converted to: {result}")
                        return result
                    else:
                        return f"contains({left}, {right})"
                elif expr.operator.lower() == "or":
                    return f"({left}) or ({right})"
                else:
                    return f"({left}) {expr.operator} ({right})"
            elif isinstance(expr, rivendel.IsFalse):
                return f"{to_odata_filter(expr.expr)} eq false"
            elif isinstance(expr, rivendel.IsTrue):
                return f"{to_odata_filter(expr.expr)} eq true"

            # If we get here, the expression type is not supported
            print(f"DEBUG: Unsupported expression type: {type(expr)}")
            print(f"DEBUG: Expression details: {expr}")
            print(f"DEBUG: Expression attributes: {dir(expr)}")

            raise Exception(
                f"Expression not supported in OData filter: {expr} ({type(expr)})"
            )

        def handle_like_expression(like_expr):
            """Handle datafusion Like expressions"""
            print(f"DEBUG: Handling LIKE expression: {like_expr}")

            # Extract left side (field) and right side (pattern)
            field_expr = like_expr.expr
            pattern = extract_datafusion_value(like_expr.pattern)

            print(f"DEBUG: LIKE field: {field_expr}, pattern: '{pattern}'")

            # Convert field to OData path and validate for Graph API
            field_path = to_odata_filter(field_expr)
            field_path = validate_graph_field_path(field_path)
            print(f"DEBUG: Field path (validated): {field_path}")

            # Graph API has very limited OData function support
            # Skip complex filters and use only basic supported operations
            # Handle array field filtering using configured array fields
            array_fields = table_config.get("array_fields", [])
            is_array_field = any(field_path.startswith(f"{af}[") for af in array_fields)

            if is_array_field:
                # Extract array name and handle array filtering
                if "[" in field_path and "]" in field_path:
                    array_name = field_path.split("[")[0]
                    # Get the configured element path for this array field
                    array_element_paths = table_config.get("array_element_paths", {})
                    element_path = array_element_paths.get(
                        array_name, "id"
                    )  # Default to id if not configured

                    # Graph API requires /any() operator for array filtering
                    if pattern.startswith("%") and pattern.endswith("%"):
                        search_term = pattern[1:-1]
                        result = f"{array_name}/any(r: contains(r/{element_path}, '{search_term}'))"
                    elif pattern.startswith("%") or pattern.endswith("%"):
                        search_term = pattern.strip("%")
                        result = f"{array_name}/any(r: contains(r/{element_path}, '{search_term}'))"
                    else:
                        result = f"{array_name}/any(r: r/{element_path} eq '{pattern}')"
                    print(
                        f"DEBUG: Array field '{field_path}' with pattern '{pattern}' using element path '{element_path}' -> {result}"
                    )
            # Convert LIKE pattern to Graph API compatible syntax for regular fields
            else:
                # Get filterable fields from config
                filterable_fields = table_config.get("filterable_fields", ["subject"])
                supported_nested_fields = table_config.get(
                    "supported_nested_fields", []
                )

                if (
                    field_path in filterable_fields
                    or field_path in supported_nested_fields
                ):
                    # Convert LIKE pattern to Graph API compatible syntax
                    if pattern.startswith("%") and pattern.endswith("%"):
                        # %text% -> contains (supported in Graph API)
                        search_term = pattern[1:-1]
                        result = f"contains({field_path}, '{search_term}')"
                    elif pattern.startswith("%") or pattern.endswith("%"):
                        # %text or text% -> use contains (endsWith/startsWith not supported for messages)
                        search_term = pattern.strip("%")
                        result = f"contains({field_path}, '{search_term}')"
                        print(
                            f"DEBUG: Converting LIKE pattern '{pattern}' to contains() since endsWith/startsWith not supported"
                        )
                    else:
                        # Exact match
                        result = f"{field_path} eq '{pattern}'"

                    # Debug output to see what we're generating
                    print(f"DEBUG: Pattern '{pattern}' -> OData: {result}")
                else:
                    # Unsupported field path
                    print(f"DEBUG: Unsupported field path: {field_path}")
                    return None

            print(f"DEBUG: LIKE converted to: {result}")
            return result

        def to_search_query(expr):
            """Convert rivendel expression to Graph API $search syntax"""
            print(f"DEBUG: Processing search expression: {expr} (type: {type(expr)})")

            # Handle DataFusion expressions using isinstance
            if isinstance(expr, rivendel.BinaryExpr):
                # Check for comparison operators first, before processing operands
                if expr.operator in [">", ">=", "<", "<=", "!=", "ne"]:
                    print(
                        f"DEBUG: Skipping comparison operator {expr.operator} in search mode"
                    )
                    return None

                # Process operands only after checking operator
                left = to_search_query(expr.left)
                right = to_search_query(expr.right)

                if expr.operator.lower() == "and":
                    return f"({left}) AND ({right})"
                elif expr.operator.lower() == "or":
                    return f"({left}) OR ({right})"
                elif (
                    expr.operator == "="
                    or expr.operator.lower() == "like"
                    or expr.operator.lower() == "~*"
                ):
                    return f"{left}:{right}"
                return None
            elif isinstance(expr, rivendel.Like):
                return handle_like_search_expression(expr)
            elif isinstance(expr, rivendel.Column):
                column_name = expr.name
                # Map to search field
                search_mappings = table_config.get("search_field_mappings", {})
                return search_mappings.get(column_name, column_name)

            elif isinstance(expr, rivendel.Literal):
                if isinstance(expr.value, str):
                    return expr.value.strip("%\"'")
                else:
                    return str(expr.value)

            # Handle DataFusion literal values
            if isinstance(expr, (rivendel.Literal, rivendel.ScalarValue)):
                return extract_datafusion_value(expr)

            # Handle DataFusion timestamp values
            if "Timestamp" in str(type(expr)) or "TimestampMicrosecond" in str(expr):
                try:
                    from datetime import datetime

                    # Extract microseconds from string representation
                    expr_str = str(expr)
                    if "TimestampMicrosecond(" in expr_str:
                        microseconds = int(expr_str.split("(")[1].split(",")[0])
                        dt = datetime.fromtimestamp(microseconds / 1000000)
                        return dt.strftime("%Y-%m-%d")
                except Exception as e:
                    print(f"DEBUG: Could not convert timestamp {expr}: {e}")
                    return None

            # Handle other DataFusion literal values
            if hasattr(expr, "value"):
                value = expr.value
                if isinstance(value, str):
                    return value.strip("%\"'")
                else:
                    return str(value)

            print(f"DEBUG: Unsupported search expression: {expr}")
            return None

        def handle_like_search_expression(like_expr):
            """Handle datafusion Like expressions for search"""
            print(f"DEBUG: Handling LIKE search expression: {like_expr}")

            field_expr = like_expr.expr
            pattern = extract_datafusion_value(like_expr.pattern)
            print(f"DEBUG: Field expression: {field_expr}, type: {type(field_expr)}")
            print(f"DEBUG: Pattern value: {pattern}")

            # Clean up pattern for search
            search_term = pattern.strip("%\"'")

            # Escape special characters for Graph API search
            search_term = escape_search_term(search_term)
            print(f"DEBUG: Cleaned and escaped search term: {search_term}")

            # Convert field to search field
            if isinstance(field_expr, rivendel.Column):
                field_name = field_expr.name
                search_mappings = table_config.get("search_field_mappings", {})
                search_field = search_mappings.get(field_name, field_name)
                print(
                    f"DEBUG: Column field '{field_name}' mapped to search field '{search_field}'"
                )
                if search_term is None:
                    print(f"DEBUG: Skipping search term due to special characters")
                    return None
                return f"{search_field}:{search_term}"
            elif isinstance(field_expr, rivendel.ScalarFunction):
                # Handle nested field access for search
                print(f"DEBUG: Processing ScalarFunction for search")
                if search_term is None:
                    print(f"DEBUG: Skipping nested search due to special characters")
                    return None
                return handle_nested_search_field(field_expr, search_term)

            print(f"DEBUG: Using default subject fallback")
            if search_term is None:
                print(f"DEBUG: Skipping default fallback due to special characters")
                return None
            return f"subject:{search_term}"  # Default fallback

        def handle_nested_search_field(func_expr, search_term):
            """Handle nested field access in search like from.emailAddress.address"""
            print(f"DEBUG: Handling nested search field: {func_expr}")

            # Extract the base field from nested get_field calls
            base_field = extract_base_field_from_nested(func_expr)
            print(f"DEBUG: Extracted base field: {base_field}")

            # Map to search field
            search_mappings = table_config.get("search_field_mappings", {})
            search_field = search_mappings.get(base_field, base_field)

            print(f"DEBUG: Mapped '{base_field}' to search field '{search_field}'")
            if search_term is None:
                print(f"DEBUG: Skipping nested search due to special characters")
                return None
            return f"{search_field}:{search_term}"

        def extract_base_field_from_nested(expr):
            """Recursively extract the base field from nested get_field expressions"""
            print(
                f"DEBUG: extract_base_field_from_nested input: {expr}, type: {type(expr)}"
            )

            if isinstance(expr, rivendel.ScalarFunction) and expr.name == "get_field":
                # This is a get_field function, get the base expression (first argument)
                if hasattr(expr, "args") and len(expr.args) > 0:
                    base_expr = expr.args[0]
                    print(f"DEBUG: get_field base expression: {base_expr}")
                    return extract_base_field_from_nested(base_expr)
            elif isinstance(expr, rivendel.Column):
                field_name = expr.name
                print(f"DEBUG: Found base Column field: {field_name}")
                return field_name

            # Fallback - try to extract from string representation
            expr_str = str(expr)
            print(f"DEBUG: Using fallback string extraction from: {expr_str}")
            if "from" in expr_str.lower():
                return "from"
            elif "recipient" in expr_str.lower():
                return "toRecipients"
            elif "subject" in expr_str.lower():
                return "subject"

            return "body"  # Final fallback

        def escape_search_term(term):
            """Escape special characters in search terms for Graph API"""
            if not term:
                return term

            # Graph API search has issues with these characters
            # Replace or escape problematic characters
            special_chars = {
                "=": "",  # Remove equals signs
                "+": "",  # Remove plus signs
                "/": "",  # Remove forward slashes
                "\\": "",  # Remove backslashes
                '"': '\\"',  # Escape quotes
                "'": "\\'",  # Escape single quotes
                "(": "\\(",  # Escape parentheses
                ")": "\\)",
                "[": "\\[",  # Escape brackets
                "]": "\\]",
                "{": "\\{",  # Escape braces
                "}": "\\}",
            }

            # For conversationId and other special fields, be more aggressive
            if len(term) > 50 or any(c in term for c in "=+/\\"):
                # This looks like an ID field with special chars - skip search for these
                print(
                    f"DEBUG: Skipping search for term with special characters: {term}"
                )
                return None

            # Apply character replacements
            escaped_term = term
            for old_char, new_char in special_chars.items():
                escaped_term = escaped_term.replace(old_char, new_char)

            return escaped_term

        def handle_get_field_function(func_expr):
            """Handle datafusion get_field scalar functions"""
            print(f"DEBUG: Handling get_field: {func_expr}")

            if not hasattr(func_expr, "args") or len(func_expr.args) < 2:
                print(f"DEBUG: get_field function has invalid args: {func_expr}")
                raise Exception(f"get_field function missing required arguments")

            args = func_expr.args
            base_expr = args[0]
            field_name = extract_datafusion_value(args[1])

            print(f"DEBUG: get_field base: {base_expr}, field: {field_name}")

            # Recursively process the base expression
            base_path = to_odata_filter(base_expr)

            # Build the full path and validate it
            result = f"{base_path}/{field_name}"
            result = validate_graph_field_path(result)
            print(f"DEBUG: get_field result: {result}")
            return result

        def handle_array_element_function(func_expr):
            """Handle datafusion array_element scalar functions for array indexing like toRecipients[0]"""
            print(f"DEBUG: Handling array_element: {func_expr}")

            if not hasattr(func_expr, "args") or len(func_expr.args) < 2:
                print(f"DEBUG: array_element function has invalid args: {func_expr}")
                raise Exception(f"array_element function missing required arguments")

            args = func_expr.args
            array_expr = args[0]  # The array field (like toRecipients)
            index_expr = args[1]  # The index (like 0)

            # Extract the array field name
            array_field = to_odata_filter(array_expr)

            # Extract the index value
            index_value = extract_datafusion_value(index_expr)

            print(f"DEBUG: array_element array: {array_field}, index: {index_value}")

            # Build the array access path
            # Graph API uses /any() operator for array filtering instead of direct indexing
            array_fields = table_config.get("array_fields", [])
            if array_field in array_fields:
                # For recipient arrays, we'll need to use /any() for filtering
                # Return a placeholder that will be handled in the LIKE processing
                result = f"{array_field}[{index_value}]"
            else:
                # For other arrays, try direct indexing (may not work in Graph API)
                result = f"{array_field}/{index_value}"

            print(f"DEBUG: array_element result: {result}")
            return result

        # Choose between filter and search based on configuration
        if use_search_param:
            # Build search expressions
            search_exprs = []

            # Add expressions from exprs parameter (these are typically search strings)
            for expr_str in exprs:
                if expr_str and expr_str.strip():
                    print(f"Adding search expression: {expr_str}")
                    search_exprs.append(expr_str)

            # Process rivendel expressions for search
            for f in filters:
                try:
                    print(f"DEBUG: Processing search filter: {f}")
                    search_query = to_search_query(f)
                    print(f"DEBUG: Converted to search: {search_query}")
                    if search_query and search_query.strip() and search_query != "None":
                        search_exprs.append(search_query)
                    else:
                        print(
                            f"DEBUG: Skipping empty or None search query: {search_query}"
                        )
                except Exception as exc:
                    print(f"Exception processing search filter {f}: {exc}")
                    import traceback

                    traceback.print_exc()
                    # will be filtered by data engine
                    pass

            # Combine all search expressions, filtering out None values
            if search_exprs:
                # Filter out any None values that might have slipped through
                valid_search_exprs = [
                    expr
                    for expr in search_exprs
                    if expr and expr.strip() and expr != "None"
                ]
                if valid_search_exprs:
                    combined_search = " AND ".join(
                        f"({expr})" for expr in valid_search_exprs
                    )
                    params["$search"] = f'"{combined_search}"'
                    print(f"Using Graph API search: {combined_search}")
                else:
                    print("DEBUG: No valid search expressions after filtering")

        elif use_filter:
            # Build filter expressions (existing logic)
            filter_exprs = []

            # Add base filter if configured
            if self._filter:
                filter_exprs.append(self._filter)

            # Add expressions from exprs parameter
            for expr_str in exprs:
                filter_exprs.append(expr_str)

            # Process rivendel filter expressions
            for f in filters:
                try:
                    print(f"DEBUG: Processing filter: {f}")
                    odata_filter = to_odata_filter(f)
                    print(f"DEBUG: Converted to OData: {odata_filter}")
                    if odata_filter and odata_filter.strip():
                        filter_exprs.append(odata_filter)
                except Exception as exc:
                    print(f"Exception processing filter {f}: {exc}")
                    import traceback

                    traceback.print_exc()
                    # will be filtered by data engine
                    pass

            # Combine all filters
            if filter_exprs:
                combined_filter = " and ".join(f"({expr})" for expr in filter_exprs)
                params["$filter"] = combined_filter
                print(f"Using OData filter: {combined_filter}")

                # Debug field path usage
                supported_nested_fields = table_config.get(
                    "supported_nested_fields", []
                )
                for nested_field in supported_nested_fields:
                    if nested_field in combined_filter:
                        print(f"DEBUG: Using configured nested field: {nested_field}")
        else:
            print("DEBUG: Both filtering and search are disabled")

        print(f"Built URL: {url} with params: {params}")

        # Debug: Show how filters were processed
        if filters:
            print("Original filters:")
            for i, f in enumerate(filters):
                print(f"  Filter {i}: {f} (type: {type(f)})")
                # Debug nested field access
                if hasattr(f, "left") and hasattr(f, "right"):
                    print(f"    Left: {f.left} (type: {type(f.left)})")
                    print(f"    Right: {f.right} (type: {type(f.right)})")
                    print(f"    Operator: {f.operator}")

        return (url, params)

    def _get_example_filters(self):
        """Return example filter expressions for common use cases"""
        import rivendel
        from datetime import datetime, timedelta

        # Example: Filter by subject containing specific text
        subject_filter = rivendel.BinaryExpr(
            left=rivendel.Column("subject"),
            operator="~*",
            right=rivendel.Literal("important"),
        )

        # Example: Filter by sender email
        from_filter = rivendel.BinaryExpr(
            left=rivendel.Column("from"),
            operator="=",
            right=rivendel.Literal("sender@example.com"),
        )

        # Example: Filter by date range (last 7 days)
        date_filter = rivendel.BinaryExpr(
            left=rivendel.Column("receivedDateTime"),
            operator=">=",
            right=rivendel.Literal(datetime.now() - timedelta(days=7)),
        )

        # Example: Filter by recipient email containing specific domain
        recipient_filter = rivendel.BinaryExpr(
            left=rivendel.ScalarFunction(
                name="array_element",
                args=[rivendel.Column("toRecipients"), rivendel.Literal(0)],
            ),
            operator="~*",
            right=rivendel.Literal("%company.com"),
        )

        return [subject_filter, from_filter, date_filter, recipient_filter]

    async def execute(self, filters, *args, **kwargs):
        limit = kwargs.get("limit", 1000)

        print(f"Execute called with {len(filters)} filters")
        for i, f in enumerate(filters):
            print(f"Filter {i}: {f} (type: {type(f)})")

        async def execute_mailbox(mailbox, limit):
            # Check if we should use search mode
            table_config = self._config
            use_search_param = table_config.get("use_search", False)

            (url, params) = self._build_url(
                mailbox,
                filters,
                self._config.get("search"),
                top=200,
                use_search=use_search_param,
            )

            print(f"Executing mailbox: {mailbox} => {url} with params: {params}")

            count = 0

            async for item in self.client.get(url, params):
                item = process_item_recursively(item)

                # Process the item (default implementation just yields the item)
                for item in self.process_item(mailbox, item):
                    yield item

                count += 1
                if limit and count > limit:
                    break

        tasks = []

        for mailbox in self._config.get("mailboxes"):
            tasks.append(execute_mailbox(mailbox, limit))

        merged = aiostream.stream.merge(*tasks)

        count = 0

        # Process data in chunks to avoid memory issues
        async with merged.stream() as streamer:
            async for chunk in chunks(streamer, self._chunk_size):
                if not chunk:  # Skip empty chunks
                    continue

                rb = pa.RecordBatch.from_pylist(chunk, schema=self._schema)
                yield rb

                count += len(chunk)

                if limit and count > limit:
                    return

    def _process_item_with_type_conversion(self, item):
        """Process an item with type conversion based on configuration.

        Args:
            item: The item to process

        Returns:
            The processed item with converted types
        """
        # If auto_convert is enabled, use recursive type conversion
        if self._auto_convert:
            return process_item_recursively(item, True)

        # Otherwise, use explicit type conversion based on configuration
        processed_item = dict(item)  # Create a copy to avoid modifying the original

        # Apply explicit type conversions if specified
        for field_path, conversion_type in self._type_conversion.items():
            parts = field_path.split(".")

            # Handle simple field
            if len(parts) == 1 and parts[0] in processed_item:
                if conversion_type == "datetime":
                    processed_item[parts[0]] = parse_date(processed_item[parts[0]])
                elif conversion_type == "int":
                    try:
                        processed_item[parts[0]] = int(processed_item[parts[0]])
                    except (ValueError, TypeError):
                        pass
                elif conversion_type == "float":
                    try:
                        processed_item[parts[0]] = float(processed_item[parts[0]])
                    except (ValueError, TypeError):
                        pass
                elif conversion_type == "bool":
                    if isinstance(processed_item[parts[0]], str):
                        processed_item[parts[0]] = processed_item[parts[0]].lower() in [
                            "true",
                            "yes",
                            "y",
                            "1",
                        ]

            # Handle nested field
            elif len(parts) > 1:
                current = processed_item
                for i, part in enumerate(parts[:-1]):
                    if part in current and isinstance(current[part], dict):
                        current = current[part]
                    else:
                        break

                last_part = parts[-1]
                if last_part in current:
                    if conversion_type == "datetime":
                        current[last_part] = parse_date(current[last_part])
                    elif conversion_type == "int":
                        try:
                            current[last_part] = int(current[last_part])
                        except (ValueError, TypeError):
                            pass
                    elif conversion_type == "float":
                        try:
                            current[last_part] = float(current[last_part])
                        except (ValueError, TypeError):
                            pass
                    elif conversion_type == "bool":
                        if isinstance(current[last_part], str):
                            current[last_part] = current[last_part].lower() in [
                                "true",
                                "yes",
                                "y",
                                "1",
                            ]

        return processed_item

    def process_item(self, item):
        """Process a single item from the API response.

        This method can be overridden by subclasses to implement custom processing.

        Args:
            item: The item from the API response

        Yields:
            Processed item(s)
        """
        yield item


class EmailTableProvider(AzureGraphTableProvider):
    """Table provider for emails."""

    def process_item(self, mailbox, item):
        body_text = item.get("body").get("content")
        if item.get("body").get("contentType") in ["html"]:
            h = html2text.HTML2Text()
            body_text = h.handle(item.get("body").get("content"))

        yield {**item, "bodyText": body_text, "mailbox": mailbox}
