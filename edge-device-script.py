# ==================== AWS CREDENTIALS SETUP ====================
def setup_aws_credentials(profile_name):
    """Set up AWS credentials for the script and KVS producer"""
    global aws_profile
    
    print(f"Setting up AWS credentials using profile: {profile_name}")
    aws_profile = profile_name
    
    try:
        # Set environment variables for AWS SDK
        os.environ['AWS_PROFILE'] = profile_name
        
        # Create a boto3 session with the specified profile
        session = boto3.Session(profile_name=profile_name)
        credentials = session.get_credentials()
        
        if not credentials:
            print(f"No credentials found for profile: {profile_name}")
            return False
            
        # Create .kvs directory if it doesn't exist
        os.makedirs(".kvs", exist_ok=True)
        
        # Write credentials to file for KVS producer
        cred_data = {
            "accessKeyId": credentials.access_key,
            "secretAccessKey": credentials.secret_key
        }
        
        # Add session token if present (for temporary credentials)
        if credentials.token:
            cred_data["sessionToken"] = credentials.token
            
        # Write credentials to file
        with open(".kvs/credential", "w") as f:
            json.dump(cred_data, f)
            
        print("AWS credentials set up successfully")
        return True
        
    except Exception as e:
        print(f"Error setting up AWS credentials: {str(e)}")
        return False
