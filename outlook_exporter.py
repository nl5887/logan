#!/usr/bin/env python3

import json
import os
import sys
import time
import urllib.parse
from loguru import logger
from firefox_cdp import FirefoxCDP


class OutlookExporter:
    def __init__(self, output_dir="exported_emails"):
        self.output_dir = output_dir
        self.firefox = None

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

    def start_browser(self):
        """Start Firefox browser with CDP enabled"""
        logger.info("Starting Firefox browser with CDP enabled")

        target_id = "BB51B5A614864DE8A273A54F159257DA"
        # target_id = 'DE92C2FB8E59CE8A159FA25155D84B34'
        # target_id = '4ADF5C335390A4CC1F1501D37E2B73DF'
        self.firefox = FirefoxCDP(
            ws_url=f"ws://host.docker.internal:9223/devtools/page/{target_id}",
            port=9222,
        )

        if False:
            if not self.firefox.start_firefox():
                logger.error("Failed to start Firefox")
                return False

        if not self.firefox.connect():
            logger.error("Failed to connect to Firefox CDP")
            return False

        # Enable necessary domains
        self.firefox.send_command("Page.enable")
        self.firefox.send_command("DOM.enable")
        self.firefox.send_command("Runtime.enable")

        if False:
            targets = self.firefox.send_command("Target.getTargets", {})
            print(targets)

            for t in targets.get("targetInfos"):
                if t.get("type") != "page":
                    continue

                print("TARGET ID", target_id)
                target_id = t.get("targetId")
                result = self.firefox.send_command(
                    "Target.attachToTarget", {"targetId": target_id, "flatten": True}
                )
                print(result)
                session_id = result.get("sessionId")

                if False:
                    print(
                        self.firefox.send_command(
                            "DOM.getDocument", {}, session_id=session_id
                        )
                    )

                if False:
                    node_id = 1

                    result = self.firefox.send_command(
                        "DOM.querySelector",
                        {
                            "nodeId": 1,
                            "selector": "iframe",
                        },
                        session_id=session_id,
                    )

                    print(result)
                    node_id = result.get("nodeId")

                    print(
                        self.firefox.send_command(
                            "DOM.getOuterHTML",
                            {
                                "nodeId": node_id,
                            },
                            session_id=session_id,
                        )
                    )

                result = self.firefox.send_command(
                    "Runtime.evaluate",
                    {
                        "expression": """
                        document.querySelector('iframe').contentWindow.document.documentElement.outerHTML
                    """,
                        "returnByValue": True,
                    },
                    session_id=session_id,
                )

                content = result.get("result").get("value")
                print("RESULT", content)

                if content:
                    frame_tree = self.firefox.send_command(
                        "Page.getFrameTree", {}, session_id=session_id
                    )
                    frame_id = (
                        frame_tree.get("frameTree", {}).get("frame", {}).get("id")
                    )

                    self.firefox.send_command(
                        "Page.setDocumentContent",
                        {
                            "html": content,
                            "frameId": frame_id,
                        },
                    )
            import sys

            sys.exit()

        return True

    def export_email_to_pdf(self, email_id, webLink=None, filename=None):
        self.start_browser()

        """Export an email to PDF by navigating directly to its Outlook Web App URL"""
        if not self.firefox and False:
            logger.error("Firefox browser not started")
            return None

        # Construct the Outlook Web App URL for the email
        url = webLink
        if url is None:
            url = f"https://outlook.office.com/mail/id/{email_id}"
        logger.info(f"Navigating to email URL: {url}")

        # Navigate to the email URL
        self.firefox.navigate_to_url(url)

        # Wait for authentication if needed
        # This is a simplified approach - in a real implementation, you would need to handle authentication
        time.sleep(5)  # Give time for the page to load and possibly authenticate

        # Check if we need to authenticate
        auth_check = self.firefox.send_command(
            "Runtime.evaluate",
            {"expression": "document.querySelector('input[type=email]') !== null"},
        )

        if auth_check and auth_check.get("result", {}).get("value", False):
            logger.warning(
                "Authentication required. Please log in manually and run again."
            )
            return None

        # Wait for the email content to load
        logger.info("Waiting for email content to load...")
        # time.sleep(3)  # Adjust as needed

        # Wait for the email to fully render
        logger.info("Runtime Evaluate")

        if True:
            self.firefox.send_command(
                "Runtime.evaluate",
                {
                    "expression": """
                new Promise(resolve => {
                    // Check if email content is loaded
                    const checkLoaded = () => {
                        const emailBody = document.querySelector('#ItemReadingPaneContainer');
                        if (emailBody && emailBody.children.length > 0) {
                            document.querySelector('button[aria-label^="Print"]').click();
                            resolve(true);
                        } else {
                            setTimeout(checkLoaded, 500);
                        }
                    };
                    checkLoaded();
                })
                """,
                    "awaitPromise": True,
                },
            )

        window = self.firefox.wait_for_method("Page.documentOpened")
        print(window)

        if False:
            parent_id = window.get("params", {}).get("frame", {}).get("parentId")

            ff2 = FirefoxCDP(
                ws_url=f"ws://host.docker.internal:9223/devtools/page/{parent_id}",
                port=9222,
            )
            ff2.connect()

            target_id = None
            url = None

            while target_id is None:
                targets = ff2.send_command("Target.getTargets", {})
                print(targets)
                targets = targets.get("targetInfos")

                for t in targets:
                    if (
                        t.get("type") == "worker"
                    ):  # and t.get('url') == 'chrome://print/':
                        target_id = t.get("targetId")
                        url = t.get("url")

                time.sleep(0.2)

            print("TARGET ID", target_id)
            result = ff2.send_command(
                "Target.attachToTarget", {"targetId": target_id, "flatten": True}
            )
            session_id = result.get("sessionId")
            print("SESSION ID", target_id)

            if False:
                print(ff2.send_command("Page.enable", session_id=session_id))
                frame_tree = ff2.send_command(
                    "Page.getFrameTree", {}, session_id=session_id
                )
                frame_id = frame_tree.get("frameTree", {}).get("frame", {}).get("id")

            ff2.send_command(
                "Runtime.evaluate",
                {
                    "expression": """
                    window.PDFViewer
                """,
                },
                session_id=session_id,
            )
            return

            result = ff2.send_command(
                "Page.getResourceContent",
                {"url": url, "frameId": frame_id},
                session_id=session_id,
            )
            url = url.replace("/0/", "/")
            print(url)
            result = ff2.send_command(
                "Page.navigate",
                {"url": url, "frameId": frame_id},
                session_id=session_id,
            )

            result = ff2.send_command(
                "Page.getResourceContent",
                {"url": url, "frameId": frame_id},
                session_id=session_id,
            )

            try:
                import base64

                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(result["content"]))

                logger.info(f"PDF saved to {file_path}")
                return file_path
            except Exception as e:
                logger.error(f"Error saving PDF: {str(e)}")
                return None

        # Save the PDF file
        if not filename:
            filename = f"email_{email_id}.pdf"

        file_path = os.path.join(self.output_dir, filename)

        result = self.firefox.send_command(
            "Runtime.evaluate",
            {
                "expression": """
                document.querySelector('iframe').contentWindow.document.documentElement.outerHTML
            """,
                "returnByValue": True,
            },
        )

        content = result.get("result").get("value")
        print("RESULT", content)

        if not content:
            raise Exception("Could not find iframe")

        frame_tree = self.firefox.send_command("Page.getFrameTree", {})
        frame_id = frame_tree.get("frameTree", {}).get("frame", {}).get("id")

        self.firefox.send_command(
            "Page.setDocumentContent",
            {
                "html": content,
                "frameId": frame_id,
            },
        )

        # Generate PDF using CDP
        logger.info("Generating PDF...")
        pdf_data = self.firefox.send_command(
            "Page.printToPDF",
            {
                "printBackground": False,
                "preferCSSPageSize": False,
                "marginTop": 0.4,
                "marginBottom": 0.4,
                "marginLeft": 0.4,
                "marginRight": 0.4,
                "paperWidth": 8.27,  # A4 width in inches
                "paperHeight": 11.69,  # A4 height in inches
            },
        )

        if not pdf_data or "data" not in pdf_data:
            logger.error("Failed to generate PDF")
            return None

        try:
            import base64

            with open(file_path, "wb") as f:
                f.write(base64.b64decode(pdf_data["data"]))

            logger.info(f"PDF saved to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error saving PDF: {str(e)}")
            return None

    def send_keyboard_shortcut(self, key_combination):
        """Send keyboard shortcuts to the active window

        Args:
            key_combination (str): Key combination to send (e.g., 'ctrl+p')

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Sending keyboard shortcut: {key_combination}")

        try:
            # Use Input.dispatchKeyEvent to simulate key presses
            # First enable the Input domain
            self.send_command("Input.enable")

            # Parse and send the key combination
            # For ctrl+p specifically
            if key_combination.lower() == "ctrl+p":
                self.send_command(
                    "Input.dispatchKeyEvent",
                    {"type": "keyDown", "modifiers": 2, "code": "KeyP"},
                )
                self.send_command(
                    "Input.dispatchKeyEvent",
                    {"type": "keyUp", "modifiers": 2, "code": "KeyP"},
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending keyboard shortcut: {str(e)}")
            return False

    def close(self):
        """Close the browser"""
        if self.firefox:
            self.firefox.close()
            self.firefox = None
