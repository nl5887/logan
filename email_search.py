#!/usr/bin/env python3

import requests
import json
import os
from datetime import datetime
from loguru import logger
from auth import GraphAuth


class EmailSearch:
    def __init__(self):
        # Initialize authentication
        self.auth = GraphAuth()
        self.base_url = "https://graph.microsoft.com/v1.0"
        # Get user ID from environment variable or use a default
        self.user_id = os.getenv("USER_ID", "me")
        logger.info(f"Using user ID: {self.user_id}")

    def search_emails(
        self, query, max_results=50, start_date=None, end_date=None, use_paging=True
    ):
        """Search for emails using Microsoft Graph API with paging support"""
        logger.info(
            f"Searching for emails with query: '{query}', max results: {max_results}"
        )

        # Build the search URL
        url = f"{self.base_url}/users/{self.user_id}/messages"
        # url = f"{self.base_url}/users/{self.user_id}/mailFolders/AAMkADYzY2U2ODE2LWEzMTEtNDI4ZS1iZThjLTRkNjliMDM1ZWZkMQAuAAAAAAAMmJML42TrQ7HInw394jgxAQDGh5fFvOjfS6HCLykwAWzDAAAjHvSeAAA%3D/messages"
        logger.info(f"API URL: {url}")

        # Prepare query parameters
        params = {
            "$top": min(
                max_results, 50
            ),  # Graph API typically limits to 50 items per request
            "$select": "id,subject,from,toRecipients,receivedDateTime,bodyPreview,body,webLink,conversationId",
        }

        conversations = {}

        # Handle search and filtering
        if query and query.strip():
            # Use search parameter
            params["$search"] = f'"{query}"'
        else:
            # If no search query, use orderby with a simple filter
            params["$filter"] = "receivedDateTime le 2024-11-05T23:59:59Z"
            params["$orderby"] = "receivedDateTime desc"

        # Add date filter if provided
        if False:
            if start_date and end_date and "$search" not in params:
                params["$filter"] = (
                    f"receivedDateTime ge {start_date}T00:00:00Z and receivedDateTime le {end_date}T23:59:59Z"
                )

        # Initialize results
        all_emails = []
        headers = self.auth.get_headers()

        if use_paging:
            # Use paging to get all results up to max_results
            next_link = None
            page_count = 0

            while len(all_emails) < max_results:
                page_count += 1

                # For the first request, use the constructed URL and params
                # For subsequent requests, use the next_link URL
                if next_link:
                    response = requests.get(next_link, headers=headers)
                else:
                    response = requests.get(url, headers=headers, params=params)

                if response.status_code == 200:
                    result = response.json()
                    page_emails = result.get("value", [])
                    for pe in page_emails:
                        if pe.get("from") is None:
                            continue

                        if (
                            pe.get("from", {}).get("emailAddress", {}).get("address")
                            is None
                        ):
                            continue

                        """
                        skip = True

                        print(pe.get('from', {}).get('emailAddress', {}).get('address'))
                        print(pe.get('toRecipients', []))
                        if 'das.nl' in pe.get('from', {}).get('emailAddress', {}).get('address'):
                            skip = False
                            for to in pe.get('toRecipients', []):
                                print(to.get('emailAddress', {}).get('address'))
                                if 'dtact.com' in to.get('emailAddress', {}).get('address'):
                                    skip = False
                            pass
                        else:
                            # if 'dtact.com' in pe.get('from', {}).get('emailAddress', {}).get('address'):
                            for to in pe.get('toRecipients', []):
                                if 'das.nl' in to.get('emailAddress', {}).get('address'):
                                    skip = False

                        if skip:
                            continue
                        """

                        received_date_time = pe.get("receivedDateTime")

                        received_date_time = received_date_time.replace("Z", "+00:00")

                        received_date_time = datetime.fromisoformat(received_date_time)

                        if (conversation_id := pe.get("conversationId")) is not None:
                            if conversation_id in conversations:
                                if conversations[conversation_id] > received_date_time:
                                    # older message of conversation
                                    logger.info(
                                        f"Skipping seen conversation: {conversation_id}"
                                    )
                                    continue
                                else:
                                    raise Exception("Got newer message of conversation")

                            conversations[conversation_id] = received_date_time
                        else:
                            raise Exception("Message contains no conversation_id")

                        import html2text

                        h = html2text.HTML2Text()
                        # print("BODY", pe.get('body'))
                        print(h.handle(pe.get("body").get("content")))
                        all_emails.extend([pe])
                        yield pe

                    logger.info(
                        f"Retrieved page {page_count} with {len(page_emails)} emails (total: {len(all_emails)})"
                    )

                    # Check if there are more pages
                    next_link = result.get("@odata.nextLink")
                    if not next_link or not page_emails:
                        break  # No more pages or empty result
                else:
                    logger.error(
                        f"Error 1searching emails: {response.status_code} - {response.text}"
                    )

                    import traceback

                    traceback.print_exc()

                    raise Exception(f"Error searching emails: {response.status_code}")
        else:
            # Single request without paging
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                all_emails = response.json().get("value", [])
            else:
                logger.error(
                    f"Error searching emails: {response.status_code} - {response.text}"
                )
                raise Exception(f"Error searching emails: {response.status_code}")

        # Limit to requested number if we got more
        if len(all_emails) > max_results:
            all_emails = all_emails[:max_results]

        logger.info(f"Found {len(all_emails)} emails matching query")
        #  return all_emails

    def search_emails_by_address(
        self, email_address, max_results=50, start_date=None, end_date=None
    ):
        """Search for emails from or to a specific email address with paging support"""
        logger.info(f"Searching for emails involving address: '{email_address}'")

        all_emails = []
        headers = self.auth.get_headers()

        # 1. Search for emails FROM the address with paging
        try:
            url = f"{self.base_url}/users/{self.user_id}/messages"
            params = {
                "$top": 50,  # Use maximum page size
                "$select": "id,subject,from,toRecipients,receivedDateTime,body,bodyPreview",
                "$filter": f"from/emailAddress/address eq '{email_address}'",
                "$orderby": "receivedDateTime desc",
            }

            # Add date filter if provided
            if start_date and end_date:
                params["$filter"] = (
                    f"from/emailAddress/address eq '{email_address}' and receivedDateTime ge {start_date}T00:00:00Z and receivedDateTime le {end_date}T23:59:59Z"
                )

            # Use paging to get all FROM emails
            next_link = None
            from_emails = []

            while len(from_emails) < max_results:
                if next_link:
                    response = requests.get(next_link, headers=headers)
                else:
                    response = requests.get(url, headers=headers, params=params)

                if response.status_code == 200:
                    result = response.json()
                    page_emails = result.get("value", [])
                    from_emails.extend(page_emails)

                    # Check if there are more pages
                    next_link = result.get("@odata.nextLink")
                    if not next_link or not page_emails:
                        break  # No more pages or empty result
                else:
                    logger.warning(
                        f"Error searching for FROM emails: {response.status_code} - {response.text}"
                    )
                    break

            logger.info(f"Found {len(from_emails)} emails FROM {email_address}")
            all_emails.extend(from_emails)
        except Exception as e:
            logger.warning(f"Error searching for emails FROM {email_address}: {str(e)}")

        # 2. Search for emails TO the address with paging
        try:
            url = f"{self.base_url}/users/{self.user_id}/messages"
            params = {
                "$top": 50,  # Use maximum page size
                "$select": "id,subject,from,toRecipients,receivedDateTime,bodyPreview,body",
                "$filter": f"toRecipients/any(r:r/emailAddress/address eq '{email_address}')",
                "$orderby": "receivedDateTime desc",
            }

            # Add date filter if provided
            if start_date and end_date:
                params["$filter"] = (
                    f"toRecipients/any(r:r/emailAddress/address eq '{email_address}') and receivedDateTime ge {start_date}T00:00:00Z and receivedDateTime le {end_date}T23:59:59Z"
                )

            # Use paging to get all TO emails
            next_link = None
            to_emails = []

            while len(to_emails) < max_results:
                if next_link:
                    response = requests.get(next_link, headers=headers)
                else:
                    response = requests.get(url, headers=headers, params=params)

                if response.status_code == 200:
                    result = response.json()
                    page_emails = result.get("value", [])
                    to_emails.extend(page_emails)

                    # Check if there are more pages
                    next_link = result.get("@odata.nextLink")
                    if not next_link or not page_emails:
                        break  # No more pages or empty result
                else:
                    logger.warning(
                        f"Error searching for TO emails: {response.status_code} - {response.text}"
                    )
                    break

            logger.info(f"Found {len(to_emails)} emails TO {email_address}")
            all_emails.extend(to_emails)
        except Exception as e:
            logger.warning(f"Error searching for emails TO {email_address}: {str(e)}")

        # Remove duplicates based on email ID
        unique_emails = {}
        for email in all_emails:
            if email["id"] not in unique_emails:
                unique_emails[email["id"]] = email

        # Sort by receivedDateTime (newest first)
        result_emails = list(unique_emails.values())
        result_emails.sort(key=lambda x: x.get("receivedDateTime", ""), reverse=True)

        # Limit to requested number
        result_emails = result_emails[:max_results]

        logger.info(
            f"Returning {len(result_emails)} unique emails involving {email_address}"
        )
        return result_emails

    def get_email_detail(self, email_id):
        """Get detailed information about a specific email"""
        logger.info(f"Getting details for email ID: {email_id}")

        url = f"{self.base_url}/users/{self.user_id}/messages/{email_id}"
        params = {
            "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,hasAttachments",
            "$expand": "attachments",
        }

        headers = self.auth.get_headers()
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            email = response.json()
            logger.info(f"Successfully retrieved email: {email['subject']}")
            return email
        else:
            logger.error(
                f"Error getting email details: {response.status_code} - {response.text}"
            )
            raise Exception(f"Error getting email details: {response.status_code}")
