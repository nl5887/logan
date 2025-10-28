# Example configuration for AzureGraphSchemaProvider

config = {
    "tables": {
        "emails": {
            "endpoint": "users/{mailbox}/messages",
            "select": "id,subject,from,toRecipients,receivedDateTime,bodyPreview,body,webLink,conversationId",
            "mailboxes": [
                "nienke.sprengers@dtact.com",
                "sander.swinkels@dtact.com",
                "remco.verhoef@dtact.com",
            ],
            "search": [
                "(participants:dossiergroep@das.nl OR participants:e.van.roosmalen@das.nl OR participants:sharon_gaillard@hotmail.com)"
            ],
            "filters": [
                """(
                contains(from/emailAddress/address, 'dossiergroep@das.nl') or
                toRecipients/any(r: contains(r/emailAddress/address, 'dossiergroep@das.nl')) or
                ccRecipients/any(r: contains(r/emailAddress/address, 'dossiergroep@das.nl')) or
                bccRecipients/any(r: contains(r/emailAddress/address, 'dossiergroep@das.nl'))
            ) or (
                contains(from/emailAddress/address, 'e.van.roosmalen@das.nl') or
                toRecipients/any(r: contains(r/emailAddress/address, 'e.van.roosmalen@das.nl')) or
                ccRecipients/any(r: contains(r/emailAddress/address, 'e.van.roosmalen@das.nl')) or
                bccRecipients/any(r: contains(r/emailAddress/address, 'e.van.roosmalen@das.nl'))
            ) or (
                contains(from/emailAddress/address, 'sharon_gaillard@hotmail.com') or
                toRecipients/any(r: contains(r/emailAddress/address, 'sharon_gaillard@hotmail.com')) or
                ccRecipients/any(r: contains(r/emailAddress/address, 'sharon_gaillard@hotmail.com')) or
                bccRecipients/any(r: contains(r/emailAddress/address, 'sharon_gaillard@hotmail.com'))
            )"""
            ],
            # Query mode configuration
            "use_filter": False,  # Disable $filter mode
            "use_search": True,  # Enable $search mode
            # Column mappings: SQL column -> Graph API field
            "column_mappings": {
                "from": "from",
                "toRecipients": "toRecipients",
                "ccRecipients": "ccRecipients",
                "bccRecipients": "bccRecipients",
                "mailbox": "mailbox",  # Custom field
                "subject": "subject",
                "bodyText": "body/content",
                "body": "body",
                "importance": "importance",
                "isRead": "isRead",
                "isDraft": "isDraft",
                "hasAttachments": "hasAttachments",
                "internetMessageId": "internetMessageId",
                "conversationId": "conversationId",
            },
            # Fields that support direct filtering with $filter
            "filterable_fields": [
                "subject",
                "importance",
                "isRead",
                "isDraft",
                "hasAttachments",
                "internetMessageId",
                "conversationId",
                "receivedDateTime",
                "sentDateTime",
                "createdDateTime",
                "lastModifiedDateTime",
            ],
            # Nested fields that are supported in Graph API filters
            "supported_nested_fields": [
                "from/emailAddress/address",
                "from/emailAddress/name",
                "body/content",
                "body/contentType",
            ],
            # Array fields that use /any() and /all() operators
            "array_fields": [
                "toRecipients",
                "ccRecipients",
                "bccRecipients",
                "attachments",
            ],
            # Field paths for array elements (for /any() operations)
            "array_element_paths": {
                "toRecipients": "emailAddress/address",
                "ccRecipients": "emailAddress/address",
                "bccRecipients": "emailAddress/address",
                "attachments": "name",
            },
            # Search field mappings: SQL field -> Graph API search field
            "search_field_mappings": {
                "from": "from",
                "sender": "from",
                "toRecipients": "participants",
                "ccRecipients": "participants",
                "bccRecipients": "participants",
                "recipients": "participants",
                "subject": "subject",
                "body": "body",
                "bodyText": "body",
                "importance": "importance",
                "isRead": "isRead",
                "receivedDateTime": "received",
                "sentDateTime": "sent",
                # Debug: Add explicit mapping to ensure from field works
                "from/emailAddress/address": "from",
                "from.emailAddress.address": "from",
            },
        },
        # Example configuration for other Graph API resources
        "users": {
            "endpoint": "users",
            "select": "id,displayName,mail,userPrincipalName,department",
            "use_filter": True,  # Users work well with $filter
            "use_search": False,
            "column_mappings": {
                "displayName": "displayName",
                "email": "mail",
                "upn": "userPrincipalName",
                "department": "department",
            },
            "filterable_fields": [
                "displayName",
                "mail",
                "userPrincipalName",
                "department",
                "accountEnabled",
            ],
            "supported_nested_fields": [],
            "array_fields": [],
            "array_element_paths": {},
            "search_field_mappings": {
                "displayName": "displayName",
                "name": "displayName",
                "email": "mail",
                "department": "department",
            },
        },
        "calendar_events": {
            "endpoint": "users/{mailbox}/events",
            "select": "id,subject,start,end,organizer,attendees",
            "use_filter": True,  # Events work with $filter
            "use_search": False,
            "column_mappings": {
                "subject": "subject",
                "startTime": "start/dateTime",
                "endTime": "end/dateTime",
                "organizer": "organizer",
                "attendees": "attendees",
            },
            "filterable_fields": ["subject", "isAllDay", "isCancelled"],
            "supported_nested_fields": [
                "start/dateTime",
                "end/dateTime",
                "organizer/emailAddress/address",
                "organizer/emailAddress/name",
            ],
            "array_fields": ["attendees"],
            "array_element_paths": {"attendees": "emailAddress/address"},
            "search_field_mappings": {
                "subject": "subject",
                "organizer": "from",
                "attendees": "participants",
            },
        },
    }
}

# Example usage documentation for different Graph API resources

"""
Usage Examples:

1. Email searching (now uses $search instead of $filter):
   SELECT * FROM emails WHERE "from"['emailAddress']['address'] LIKE '%das.nl'
   -> $search="from:das.nl"

   SELECT * FROM emails WHERE toRecipients[0]['emailAddress']['address'] = 'user@company.com'
   -> $search="participants:user@company.com"

   SELECT * FROM emails WHERE subject LIKE '%meeting%'
   -> $search="subject:meeting"

2. User filtering:
   SELECT * FROM users WHERE displayName LIKE '%John%'
   -> $filter=contains(displayName, 'John')

   SELECT * FROM users WHERE department = 'Engineering'
   -> $filter=department eq 'Engineering'

3. Calendar event filtering:
   SELECT * FROM calendar_events WHERE subject LIKE '%meeting%'
   -> $filter=contains(subject, 'meeting')

   SELECT * FROM calendar_events WHERE attendees[0]['emailAddress']['address'] LIKE '%company.com'
   -> $filter=attendees/any(r: contains(r/emailAddress/address, 'company.com'))

Configuration Fields:
- use_filter: Enable/disable $filter mode (default: True)
- use_search: Enable/disable $search mode (default: False)
- column_mappings: Maps SQL column names to Graph API field names
- search_field_mappings: Maps SQL fields to Graph API search keywords
- filterable_fields: Fields that support direct OData filtering (filter mode)
- supported_nested_fields: Nested paths like "from/emailAddress/address" (filter mode)
- array_fields: Fields that are arrays and use /any() or /all() operators (filter mode)
- array_element_paths: Paths within array elements for filtering (filter mode)

Search Keywords (when use_search=True):
- from: Sender email address
- participants: Any email participant (to/cc/bcc/from)
- subject: Email subject line
- body: Email body content
- received/sent: Date filtering

Adding New Resources:
1. Add new table configuration with endpoint and field mappings
2. Choose between use_filter=True or use_search=True
3. Configure appropriate field mappings for chosen mode
4. Test with sample queries
"""
