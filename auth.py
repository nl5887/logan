#!/usr/bin/env python3

import os
import msal
import json
from loguru import logger


class GraphAuth:
    def __init__(self):
        # Load configuration from environment variables
        self.tenant_id = os.getenv("TENANT_ID")
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = ["https://graph.microsoft.com/.default"]

        # Validate configuration
        if not all([self.tenant_id, self.client_id]):
            logger.error(
                "Missing required environment variables. Please check .env file."
            )
            raise ValueError("Missing authentication configuration")

        # Initialize MSAL app
        # For client credentials flow (app permissions)
        self.app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority,
        )

        self.token = None

    def get_token(self):
        """Get an access token for Microsoft Graph API using client credentials flow"""
        if self.token and not self._is_token_expired():
            return self.token

        # Use client credentials flow for app permissions
        logger.info("Acquiring token using client credentials flow")
        result = self.app.acquire_token_for_client(scopes=self.scopes)

        if "access_token" in result:
            self.token = result["access_token"]
            logger.info("Successfully acquired token via client credentials flow")
            return self.token
        else:
            logger.error(
                f"Failed to acquire token: {result.get('error')}, {result.get('error_description')}"
            )
            raise Exception(f"Failed to acquire token: {result.get('error')}")

    def _is_token_expired(self):
        """Check if the current token is expired"""
        # Implement token expiration check if needed
        # For simplicity, we'll always get a new token
        return True

    def get_headers(self):
        """Get headers for Microsoft Graph API requests"""
        token = self.get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
