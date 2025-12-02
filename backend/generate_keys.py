#!/usr/bin/env python3
"""
Script to generate secure Django SECRET_KEY and FIELD_ENCRYPTION_KEY
"""

import secrets
import string
import argparse
import sys
import base64

def generate_secret_key(length=50):
    """
    Generate a secure random secret key suitable for Django.
    
    Args:
        length (int): Length of the secret key (default: 50)
    
    Returns:
        str: A secure random string
    """
    # Characters to use for the secret key
    characters = string.ascii_letters + string.digits + string.punctuation
    
    # Generate cryptographically secure random string
    secret_key = ''.join(secrets.choice(characters) for _ in range(length))
    
    return secret_key

def generate_encryption_key():
    """
    Generate a secure encryption key for django-encrypted-model-fields.
    
    The key must be 32 url-safe base64-encoded bytes (44 characters).
    
    Returns:
        str: A base64 encoded 32-byte string (44 characters)
    """
    # Generate 32 random bytes
    random_bytes = secrets.token_bytes(32)
    
    # Encode to URL-safe base64 to get the proper format
    # This will create a 44-character string that django-encrypted-model-fields expects
    encryption_key = base64.urlsafe_b64encode(random_bytes).decode('ascii')
    
    return encryption_key

def validate_encryption_key(key):
    """
    Validate that the encryption key meets django-encrypted-model-fields requirements.
    
    Args:
        key (str): The encryption key to validate
    
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        # Check if it's proper base64
        decoded = base64.urlsafe_b64decode(key)
        # Should be 32 bytes when decoded
        return len(decoded) == 32
    except Exception:
        return False

def generate_env_file(secret_key, encryption_key, filename='.env'):
    """
    Generate or update a .env file with SECRET_KEY and FIELD_ENCRYPTION_KEY.
    
    Args:
        secret_key (str): The generated secret key
        encryption_key (str): The generated encryption key
        filename (str): The name of the environment file
    """
    try:
        # Read existing .env file if it exists
        existing_content = {}
        other_lines = []
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        existing_content[key] = value
                    else:
                        other_lines.append(line)
        except FileNotFoundError:
            pass
        
        # Update or add SECRET_KEY and FIELD_ENCRYPTION_KEY
        existing_content['SECRET_KEY'] = secret_key
        existing_content['FIELD_ENCRYPTION_KEY'] = encryption_key
        
        # Write back to file
        with open(filename, 'w') as f:
            f.write("# Django Security Keys (automatically generated)\n")
            f.write("# DO NOT COMMIT THESE TO VERSION CONTROL!\n\n")
            
            f.write("# Django Secret Key\n")
            f.write(f"SECRET_KEY={secret_key}\n\n")
            
            f.write("# Field Encryption Key (for django-encrypted-model-fields)\n")
            f.write(f"FIELD_ENCRYPTION_KEY={encryption_key}\n\n")
            
            # Write other existing content (comments, empty lines, etc.)
            if other_lines:
                f.write("# Existing configuration\n")
                for line in other_lines:
                    f.write(f"{line}\n")
                f.write("\n")
            
            f.write("# Application configuration\n")
            # Write other existing variables (excluding the ones we just wrote)
            other_vars_written = False
            for key, value in existing_content.items():
                if key not in ['SECRET_KEY', 'FIELD_ENCRYPTION_KEY']:
                    f.write(f"{key}={value}\n")
                    other_vars_written = True
            
            if not other_vars_written:
                f.write("# Add your other environment variables below\n")
                f.write("DEBUG=True\n")
                f.write("ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0\n")
                f.write("DB_NAME=docbiz_db\n")
                f.write("DB_USER=docbiz_user\n")
                f.write("DB_PASSWORD=docbiz123\n")
                f.write("DB_HOST=localhost\n")
                f.write("DB_PORT=5432\n")
                f.write("CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000\n")
        
        # Validate the generated key
        is_valid = validate_encryption_key(encryption_key)
        
        print(f"✅ SECRET_KEY and FIELD_ENCRYPTION_KEY generated and saved to {filename}")
        print(f"🔑 SECRET_KEY: {secret_key}")
        print(f"🔐 FIELD_ENCRYPTION_KEY: {encryption_key}")
        print(f"📏 FIELD_ENCRYPTION_KEY length: {len(encryption_key)} characters")
        
        if is_valid:
            print("✅ FIELD_ENCRYPTION_KEY validation: PASSED")
        else:
            print("❌ FIELD_ENCRYPTION_KEY validation: FAILED")
            print("   The key may not work with django-encrypted-model-fields")
        
    except Exception as e:
        print(f"❌ Error writing to {filename}: {e}")
        return False
    
    return True

def fix_existing_env_file(filename='.env'):
    """
    Fix an existing .env file by generating a valid FIELD_ENCRYPTION_KEY.
    
    Args:
        filename (str): The name of the .env file to fix
    """
    try:
        # Read existing content
        with open(filename, 'r') as f:
            content = f.read()
        
        # Generate a valid encryption key
        new_encryption_key = generate_encryption_key()
        
        # Replace the existing FIELD_ENCRYPTION_KEY
        import re
        if 'FIELD_ENCRYPTION_KEY=' in content:
            new_content = re.sub(
                r'FIELD_ENCRYPTION_KEY=.*',
                f'FIELD_ENCRYPTION_KEY={new_encryption_key}',
                content
            )
        else:
            # Add it if it doesn't exist
            new_content = content + f"\n# Field Encryption Key (fixed)\nFIELD_ENCRYPTION_KEY={new_encryption_key}\n"
        
        # Write back to file
        with open(filename, 'w') as f:
            f.write(new_content)
        
        print(f"✅ Fixed FIELD_ENCRYPTION_KEY in {filename}")
        print(f"🔐 New FIELD_ENCRYPTION_KEY: {new_encryption_key}")
        print(f"📏 Length: {len(new_encryption_key)} characters")
        
        # Validate
        is_valid = validate_encryption_key(new_encryption_key)
        if is_valid:
            print("✅ Key validation: PASSED - Ready to use with django-encrypted-model-fields")
        else:
            print("❌ Key validation: FAILED")
            
        return True
        
    except Exception as e:
        print(f"❌ Error fixing {filename}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Generate secure Django SECRET_KEY and FIELD_ENCRYPTION_KEY')
    parser.add_argument('--length', type=int, default=50, 
                       help='Length of the secret key (default: 50)')
    parser.add_argument('--env-file', type=str, default='.env',
                       help='Name of the .env file (default: .env)')
    parser.add_argument('--show-only', action='store_true',
                       help='Only show the keys without saving to file')
    parser.add_argument('--encryption-only', action='store_true',
                       help='Only generate FIELD_ENCRYPTION_KEY')
    parser.add_argument('--secret-only', action='store_true',
                       help='Only generate SECRET_KEY')
    parser.add_argument('--fix-encryption', action='store_true',
                       help='Fix existing FIELD_ENCRYPTION_KEY in .env file')
    
    args = parser.parse_args()
    
    # Handle fix encryption mode
    if args.fix_encryption:
        success = fix_existing_env_file(args.env_file)
        if success:
            print("\n💡 Important: If you have existing encrypted data, it will become unreadable!")
            print("   You'll need to either:")
            print("   1. Migrate your data before changing the key")
            print("   2. Accept that existing encrypted data will be lost")
            print("   3. Keep using the old key (if you have a backup)")
        return
    
    # Generate keys based on arguments
    if args.encryption_only:
        encryption_key = generate_encryption_key()
        if args.show_only:
            print(f"🔐 Generated FIELD_ENCRYPTION_KEY: {encryption_key}")
            print(f"📏 Length: {len(encryption_key)} characters")
            print(f"✅ Valid: {validate_encryption_key(encryption_key)}")
        else:
            # For encryption-only, we need to preserve existing SECRET_KEY if it exists
            try:
                with open(args.env_file, 'r') as f:
                    content = f.read()
            except FileNotFoundError:
                content = ""
            
            # Extract existing SECRET_KEY if present
            existing_secret_key = None
            for line in content.split('\n'):
                if line.startswith('SECRET_KEY='):
                    existing_secret_key = line.split('=', 1)[1]
                    break
            
            if existing_secret_key:
                success = generate_env_file(existing_secret_key, encryption_key, args.env_file)
            else:
                print("❌ No existing SECRET_KEY found. Please generate both keys together.")
                sys.exit(1)
    
    elif args.secret_only:
        secret_key = generate_secret_key(args.length)
        if args.show_only:
            print(f"🔑 Generated SECRET_KEY: {secret_key}")
            print(f"📏 Length: {len(secret_key)} characters")
        else:
            # For secret-only, we need to preserve existing FIELD_ENCRYPTION_KEY if it exists
            try:
                with open(args.env_file, 'r') as f:
                    content = f.read()
            except FileNotFoundError:
                content = ""
            
            # Extract existing FIELD_ENCRYPTION_KEY if present
            existing_encryption_key = None
            for line in content.split('\n'):
                if line.startswith('FIELD_ENCRYPTION_KEY='):
                    existing_encryption_key = line.split('=', 1)[1]
                    break
            
            if existing_encryption_key:
                # Validate the existing key
                if validate_encryption_key(existing_encryption_key):
                    success = generate_env_file(secret_key, existing_encryption_key, args.env_file)
                else:
                    print("❌ Existing FIELD_ENCRYPTION_KEY is invalid. Use --fix-encryption to generate a new one.")
                    sys.exit(1)
            else:
                print("❌ No existing FIELD_ENCRYPTION_KEY found. Please generate both keys together.")
                sys.exit(1)
    
    else:
        # Generate both keys
        secret_key = generate_secret_key(args.length)
        encryption_key = generate_encryption_key()
        
        if args.show_only:
            print(f"🔑 Generated SECRET_KEY: {secret_key}")
            print(f"📏 SECRET_KEY length: {len(secret_key)} characters")
            print(f"🔐 Generated FIELD_ENCRYPTION_KEY: {encryption_key}")
            print(f"📏 FIELD_ENCRYPTION_KEY length: {len(encryption_key)} characters")
            print(f"✅ FIELD_ENCRYPTION_KEY valid: {validate_encryption_key(encryption_key)}")
        else:
            success = generate_env_file(secret_key, encryption_key, args.env_file)
            if success:
                print("💡 Tip: Keep these keys secure and never commit them to version control!")
                print("💡 Note: FIELD_ENCRYPTION_KEY must be 32 url-safe base64-encoded bytes")

if __name__ == "__main__":
    main()