#!/usr/bin/env python3
"""
Script to find correct AWS Bedrock model IDs and inference profiles
Helps resolve "inference profile" and "invalid model identifier" errors
"""

import boto3
import json
from botocore.exceptions import ClientError, NoCredentialsError
import os
import sys


def check_aws_setup():
    """Check if AWS is properly configured"""
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        if credentials is None:
            return False, "No AWS credentials found"

        # Test with STS
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        region = session.region_name or os.environ.get(
            "AWS_DEFAULT_REGION", "us-east-1"
        )

        return True, {
            "account": identity.get("Account"),
            "user_arn": identity.get("Arn"),
            "region": region,
        }
    except Exception as e:
        return False, f"AWS setup error: {str(e)}"


def list_foundation_models(region="us-east-1"):
    """List available foundation models in region"""
    print(f"\n🤖 Foundation Models in {region}:")
    print("-" * 40)

    try:
        bedrock = boto3.client("bedrock", region_name=region)
        response = bedrock.list_foundation_models()

        models = response.get("modelSummaries", [])
        if not models:
            print(f"❌ No foundation models found in {region}")
            return []

        # Group by provider
        providers = {}
        for model in models:
            provider = model.get("providerName", "Unknown")
            if provider not in providers:
                providers[provider] = []
            providers[provider].append(model)

        valid_models = []
        for provider, provider_models in providers.items():
            print(f"\n📦 {provider} ({len(provider_models)} models):")

            for model in provider_models:
                model_id = model["modelId"]
                model_name = model.get("modelName", "Unknown")

                # Check if model supports streaming
                supports_streaming = "TEXT" in model.get("outputModalities", [])
                streaming_icon = "🌊" if supports_streaming else "📄"

                print(f"  {streaming_icon} {model_name}")
                print(f"     ID: {model_id}")

                # Test if we can actually invoke this model
                access_status = test_model_access(model_id, region)
                print(f"     Access: {access_status}")

                if "✅" in access_status:
                    valid_models.append(
                        {
                            "id": model_id,
                            "name": model_name,
                            "provider": provider,
                            "streaming": supports_streaming,
                        }
                    )
                print()

        return valid_models

    except ClientError as e:
        print(f"❌ Error listing models: {e}")
        return []


def list_inference_profiles(region="us-east-1"):
    """List inference profiles (newer AWS Bedrock feature)"""
    print(f"\n🎯 Inference Profiles in {region}:")
    print("-" * 35)

    try:
        bedrock = boto3.client("bedrock", region_name=region)

        # This is a newer API, might not be available in all SDKs
        try:
            response = bedrock.list_inference_profiles()
            profiles = response.get("inferenceProfileSummaries", [])

            if not profiles:
                print("ℹ️  No inference profiles found")
                return []

            valid_profiles = []
            for profile in profiles:
                profile_id = profile.get("inferenceProfileId")
                profile_name = profile.get("inferenceProfileName", "Unknown")
                models = profile.get("models", [])

                print(f"🎯 {profile_name}")
                print(f"   ID: {profile_id}")
                print(f"   Models: {len(models)}")
                for model in models[:3]:  # Show first 3 models
                    print(f"     - {model.get('modelId', 'Unknown')}")
                if len(models) > 3:
                    print(f"     ... and {len(models) - 3} more")

                # Test profile access
                access_status = test_model_access(profile_id, region)
                print(f"   Access: {access_status}")

                if "✅" in access_status:
                    valid_profiles.append(
                        {
                            "id": profile_id,
                            "name": profile_name,
                            "models": [m.get("modelId") for m in models],
                        }
                    )
                print()

            return valid_profiles

        except AttributeError:
            print("ℹ️  Inference profiles API not available in this SDK version")
            return []
        except ClientError as e:
            if "UnknownOperationException" in str(e):
                print("ℹ️  Inference profiles not supported in this region")
            else:
                print(f"⚠️  Error listing inference profiles: {e}")
            return []

    except Exception as e:
        print(f"❌ Error checking inference profiles: {e}")
        return []


def test_model_access(model_id, region):
    """Test if we can actually access a model"""
    try:
        bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)

        # Try a minimal invoke to test access
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(
                {
                    "inputText": "Hello",
                    "textGenerationConfig": {"maxTokenCount": 1, "temperature": 0},
                }
            )
            if "titan" in model_id.lower()
            else json.dumps(
                {"prompt": "Hello", "max_tokens_to_sample": 1, "temperature": 0}
            ),
        )
        return "✅ Accessible"

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDeniedException":
            return "❌ Access denied - request model access"
        elif error_code == "ValidationException":
            if "inference profile" in str(e).lower():
                return "⚠️  Requires inference profile"
            else:
                return "❌ Invalid model ID"
        elif error_code == "ThrottlingException":
            return "⚠️  Rate limited (but accessible)"
        else:
            return f"❌ Error: {error_code}"

    except Exception as e:
        return f"❌ Unknown error: {str(e)[:50]}..."


def get_recommended_models():
    """Get recommended model IDs for Logan"""
    return {
        "Claude 3 Models (Best for coding)": [
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-opus-20240229-v1:0",
        ],
        "Claude 2 Models (Reliable)": ["anthropic.claude-v2:1", "anthropic.claude-v2"],
        "Amazon Titan (Always available)": [
            "amazon.titan-text-express-v1",
            "amazon.titan-text-lite-v1",
        ],
        "Meta Llama": ["meta.llama2-13b-chat-v1", "meta.llama2-70b-chat-v1"],
    }


def suggest_logan_commands(valid_models):
    """Suggest working Logan commands"""
    print(f"\n🚀 Working Logan Commands:")
    print("=" * 30)

    if not valid_models:
        print("❌ No accessible models found!")
        print("\nOptions:")
        print("1. Use mock mode: python3 logan.py --model mock")
        print("2. Request model access in AWS Bedrock console")
        return

    # Prioritize by preference
    model_priority = [
        "anthropic.claude-3-haiku-20240307-v1:0",
        "anthropic.claude-3-sonnet-20240229-v1:0",
        "amazon.titan-text-express-v1",
        "anthropic.claude-v2:1",
    ]

    recommended = []
    for priority_model in model_priority:
        for model in valid_models:
            if model["id"] == priority_model:
                recommended.append(model)
                break

    # Add any other accessible models
    for model in valid_models:
        if model not in recommended:
            recommended.append(model)

    print("✅ Ready to use:")
    for i, model in enumerate(recommended[:5], 1):  # Show top 5
        streaming = "🌊 Streaming" if model["streaming"] else "📄 Non-streaming"
        print(f"\n{i}. {model['name']} ({streaming})")
        print(f"   python3 logan.py --model {model['id']}")

    if len(valid_models) > 5:
        print(f"\n... and {len(valid_models) - 5} more models available")


def check_specific_model(model_id, region="us-east-1"):
    """Check a specific model ID"""
    print(f"\n🔍 Checking specific model: {model_id}")
    print("-" * 50)

    # Check if it's in foundation models
    try:
        bedrock = boto3.client("bedrock", region_name=region)
        response = bedrock.list_foundation_models()

        found_model = None
        for model in response.get("modelSummaries", []):
            if model["modelId"] == model_id:
                found_model = model
                break

        if found_model:
            print("✅ Model found in foundation models")
            print(f"   Name: {found_model.get('modelName')}")
            print(f"   Provider: {found_model.get('providerName')}")
            access_status = test_model_access(model_id, region)
            print(f"   Access: {access_status}")
        else:
            print("❌ Model not found in foundation models")
            print("   This might be an inference profile ID")

            # Check if it's an inference profile
            profiles = list_inference_profiles(region)
            for profile in profiles:
                if profile["id"] == model_id:
                    print("✅ Found as inference profile")
                    break
            else:
                print("❌ Not found as inference profile either")
                print(f"\nSuggestions:")
                print("1. Check the model ID spelling")
                print("2. Try a different region")
                print("3. Use one of the recommended models above")

    except Exception as e:
        print(f"❌ Error checking model: {e}")


def main():
    print("🔍 AWS Bedrock Model Finder")
    print("=" * 40)
    print("Finding correct model IDs and inference profiles for Logan")

    # Check AWS setup
    print("\n🔐 AWS Configuration:")
    is_configured, config_info = check_aws_setup()

    if not is_configured:
        print(f"❌ {config_info}")
        print("\nPlease configure AWS first:")
        print("  aws configure")
        print("  # OR set environment variables:")
        print("  export AWS_ACCESS_KEY_ID=your_key")
        print("  export AWS_SECRET_ACCESS_KEY=your_secret")
        return

    print(f"✅ AWS configured")
    print(f"   Account: {config_info['account']}")
    print(f"   Region: {config_info['region']}")

    # Check if user wants to test a specific model
    if len(sys.argv) > 1:
        model_to_check = sys.argv[1]
        check_specific_model(model_to_check, config_info["region"])
        return

    # List available models
    valid_models = list_foundation_models(config_info["region"])

    # List inference profiles (newer feature)
    valid_profiles = list_inference_profiles(config_info["region"])

    # Show recommended models
    print(f"\n📋 Recommended Model IDs:")
    print("-" * 25)
    recommended = get_recommended_models()
    for category, models in recommended.items():
        print(f"\n{category}:")
        for model_id in models:
            print(f"  • {model_id}")

    # Suggest working commands
    suggest_logan_commands(valid_models)

    # Final troubleshooting tips
    print(f"\n💡 Troubleshooting Tips:")
    print("=" * 25)
    print("1. If no models are accessible:")
    print("   → Go to AWS Bedrock Console → Model access")
    print("   → Request access to models you want to use")

    print("\n2. If you see 'inference profile' errors:")
    print("   → Use the profile ID instead of model ID")
    print("   → Check the inference profiles listed above")

    print("\n3. To check a specific model:")
    print("   python3 find_bedrock_models.py <model-id>")

    print("\n4. To use Logan without AWS:")
    print("   python3 logan.py --model mock")

    print(f"\n5. Common working regions:")
    print("   • us-east-1 (most models)")
    print("   • us-west-2 (most models)")
    print("   • eu-west-1 (limited models)")


if __name__ == "__main__":
    main()
