#!/usr/bin/env python3
"""
Script to check available AWS Bedrock models in your current region
This helps diagnose "The provided model identifier is invalid" errors
"""

import boto3
import json
from botocore.exceptions import ClientError, NoCredentialsError, CredentialsNotFound
import os


def check_aws_credentials():
    """Check if AWS credentials are configured"""
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        if credentials is None:
            return False, "No AWS credentials found"

        # Test credentials by making a simple call
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        return True, f"Authenticated as: {identity.get('Arn', 'Unknown')}"
    except (NoCredentialsError, CredentialsNotFound):
        return False, "AWS credentials not configured"
    except Exception as e:
        return False, f"Credential check failed: {str(e)}"


def get_bedrock_regions():
    """Get regions where Bedrock is available"""
    # Known regions with Bedrock support
    bedrock_regions = [
        "us-east-1",  # N. Virginia - Most models
        "us-west-2",  # Oregon - Most models
        "eu-west-1",  # Ireland - Limited models
        "ap-southeast-1",  # Singapore - Limited models
        "ap-northeast-1",  # Tokyo - Limited models
        "eu-central-1",  # Frankfurt - Limited models
    ]
    return bedrock_regions


def check_models_in_region(region_name):
    """Check available models in a specific region"""
    try:
        print(f"\n🌍 Checking region: {region_name}")
        client = boto3.client("bedrock", region_name=region_name)

        # List foundation models
        response = client.list_foundation_models()
        models = response.get("modelSummaries", [])

        if not models:
            print(f"   ❌ No models available or region not accessible")
            return []

        print(f"   ✅ Found {len(models)} models")

        # Group models by provider
        providers = {}
        for model in models:
            provider = model.get("providerName", "Unknown")
            if provider not in providers:
                providers[provider] = []
            providers[provider].append(model)

        # Display models by provider
        available_models = []
        for provider, provider_models in providers.items():
            print(f"\n   📦 {provider} ({len(provider_models)} models):")
            for model in provider_models:
                model_id = model["modelId"]
                model_name = model.get("modelName", "Unknown")
                input_modalities = ", ".join(model.get("inputModalities", []))
                output_modalities = ", ".join(model.get("outputModalities", []))

                print(f"      🤖 {model_name}")
                print(f"         ID: {model_id}")
                print(f"         Input: {input_modalities}")
                print(f"         Output: {output_modalities}")

                available_models.append(
                    {
                        "id": model_id,
                        "name": model_name,
                        "provider": provider,
                        "region": region_name,
                    }
                )
                print()

        return available_models

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "UnauthorizedOperation":
            print(
                f"   ❌ Access denied - check IAM permissions for Bedrock in {region_name}"
            )
        elif error_code == "OptInRequired":
            print(f"   ❌ Region {region_name} requires opt-in")
        else:
            print(f"   ❌ Error: {e}")
        return []
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return []


def check_model_access(region_name):
    """Check which models you have access to (vs just listed)"""
    try:
        client = boto3.client("bedrock", region_name=region_name)

        # This endpoint shows models you actually have access to
        response = client.get_model_invocation_logging_configuration()
        print(f"   📋 Model access configuration retrieved for {region_name}")

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"   ℹ️  No model access logging configured in {region_name}")
        else:
            print(f"   ⚠️  Could not check model access: {e}")
    except Exception as e:
        print(f"   ⚠️  Error checking model access: {e}")


def suggest_logan_models(all_models):
    """Suggest models that work well with Logan"""

    preferred_models = [
        # Claude 3 family (best for coding)
        "anthropic.claude-3-haiku-20240307-v1:0",
        "anthropic.claude-3-sonnet-20240229-v1:0",
        "anthropic.claude-3-opus-20240229-v1:0",
        # Claude 2.1 (reliable fallback)
        "anthropic.claude-v2:1",
        "anthropic.claude-v2",
        # Amazon Titan (always available)
        "amazon.titan-text-express-v1",
        "amazon.titan-text-lite-v1",
    ]

    print(f"\n🎯 Recommended Models for Logan:")
    print("=" * 50)

    available_preferred = []
    for model_info in all_models:
        if model_info["id"] in preferred_models:
            available_preferred.append(model_info)

    if available_preferred:
        print("✅ These recommended models are available:")
        for model_info in available_preferred:
            print(f"   🤖 {model_info['name']}")
            print(f"      Command: python3 logan.py --model {model_info['id']}")
            print(f"      Region: {model_info['region']}")
            print()
    else:
        print("⚠️  None of the preferred models are available.")
        print("   You may need to request model access in the AWS Bedrock console.")

    # Show any available models
    if all_models:
        print("\n📋 All Available Models:")
        for model_info in all_models:
            print(
                f"   • {model_info['id']} ({model_info['provider']}) - {model_info['region']}"
            )


def check_environment():
    """Check environment variables and configuration"""
    print("\n🔧 Environment Check:")
    print("=" * 30)

    # Check AWS region
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    if region:
        print(f"✅ AWS_DEFAULT_REGION: {region}")
    else:
        print("⚠️  No AWS_DEFAULT_REGION set")

    # Check AWS profile
    profile = os.environ.get("AWS_PROFILE")
    if profile:
        print(f"✅ AWS_PROFILE: {profile}")
    else:
        print("ℹ️  Using default AWS profile")

    # Check Logan environment variables
    logan_vars = ["REPOSITORY_URL", "REPOSITORY_AUTH", "REPOSITORY_BRANCH", "COMMIT_ID"]

    print("\n📋 Logan Configuration:")
    for var in logan_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: {value}")
        else:
            print(f"ℹ️  {var}: Not set")


def main():
    print("🚀 AWS Bedrock Model Availability Checker")
    print("=" * 60)
    print("This script helps diagnose 'model identifier is invalid' errors")

    # Check AWS credentials
    print("\n🔐 AWS Credentials Check:")
    print("-" * 30)
    has_creds, creds_info = check_aws_credentials()
    if has_creds:
        print(f"✅ {creds_info}")
    else:
        print(f"❌ {creds_info}")
        print("\nTo fix:")
        print("1. Run: aws configure")
        print(
            "2. Or set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
        )
        print("3. Or use IAM roles if running on EC2")
        return

    # Check environment
    check_environment()

    # Check models in all Bedrock regions
    print(f"\n🌐 Checking Bedrock Models Across Regions:")
    print("=" * 50)

    all_available_models = []
    bedrock_regions = get_bedrock_regions()

    for region in bedrock_regions:
        models = check_models_in_region(region)
        all_available_models.extend(models)

        # Check model access
        if models:
            check_model_access(region)

    # Provide recommendations
    if all_available_models:
        suggest_logan_models(all_available_models)
    else:
        print("\n❌ No Bedrock models found in any region!")
        print("\nTroubleshooting steps:")
        print("1. Check that you're in a supported region")
        print("2. Request model access in AWS Bedrock console")
        print("3. Verify IAM permissions for Bedrock")
        print("4. Try a different AWS region")

    # Final recommendations
    print(f"\n💡 Next Steps:")
    print("=" * 20)
    print("1. If no models are available:")
    print("   - Go to AWS Bedrock Console → Model access")
    print("   - Request access to Claude 3 Haiku or Titan models")
    print("   - Wait for approval (usually instant for Titan)")

    print("\n2. To use Logan with a specific model:")
    print("   python3 logan.py --model <model-id>")

    print("\n3. To use Logan with mock mode (no AWS required):")
    print("   python3 logan.py --model mock")

    print(f"\n4. Recommended regions for most models:")
    print("   - us-east-1 (N. Virginia)")
    print("   - us-west-2 (Oregon)")


if __name__ == "__main__":
    main()
