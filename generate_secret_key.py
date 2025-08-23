#!/usr/bin/env python3
"""
Secure Secret Key Generator for HomeChef Companion Backend

This script generates cryptographically secure secret keys for JWT signing
and other security purposes in your FastAPI application.
"""

import secrets
import os
import base64
import hashlib
import sys
from typing import Optional

class SecretKeyGenerator:
    """Generate and validate cryptographically secure secret keys"""
    
    MIN_KEY_LENGTH = 32  # 256 bits minimum
    RECOMMENDED_LENGTH = 64  # 512 bits recommended
    
    @classmethod
    def generate_urlsafe_key(cls, length: int = RECOMMENDED_LENGTH) -> str:
        """
        Generate a URL-safe base64 encoded secret key using Python's secrets module
        This is the recommended method for FastAPI applications.
        
        Args:
            length: Length in bytes (default 64 = 512 bits)
            
        Returns:
            URL-safe base64 encoded secret key
        """
        return secrets.token_urlsafe(length)
    
    @classmethod
    def generate_hex_key(cls, length: int = RECOMMENDED_LENGTH) -> str:
        """
        Generate a hexadecimal secret key
        
        Args:
            length: Length in bytes (default 64 = 512 bits)
            
        Returns:
            Hexadecimal encoded secret key
        """
        return secrets.token_hex(length)
    
    @classmethod
    def generate_bytes_key(cls, length: int = RECOMMENDED_LENGTH) -> str:
        """
        Generate a secret key from random bytes and encode as base64
        
        Args:
            length: Length in bytes (default 64 = 512 bits)
            
        Returns:
            Base64 encoded secret key
        """
        random_bytes = os.urandom(length)
        return base64.b64encode(random_bytes).decode('utf-8')
    
    @classmethod
    def validate_key_strength(cls, key: str) -> dict:
        """
        Validate the strength and properties of a secret key
        
        Args:
            key: The secret key to validate
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'length_bytes': len(key.encode('utf-8')),
            'length_bits': len(key.encode('utf-8')) * 8,
            'meets_minimum': False,
            'recommended_strength': False,
            'entropy_estimate': 0,
            'warnings': [],
            'valid': False
        }
        
        # Check length requirements
        if results['length_bytes'] >= cls.MIN_KEY_LENGTH:
            results['meets_minimum'] = True
        else:
            results['warnings'].append(f"Key is too short. Minimum {cls.MIN_KEY_LENGTH} bytes required.")
        
        if results['length_bytes'] >= cls.RECOMMENDED_LENGTH:
            results['recommended_strength'] = True
        else:
            results['warnings'].append(f"Consider using {cls.RECOMMENDED_LENGTH} bytes for better security.")
        
        # Estimate entropy (simplified)
        unique_chars = len(set(key))
        results['entropy_estimate'] = unique_chars * len(key)
        
        # Check for weak patterns
        if key.lower() == key or key.upper() == key:
            results['warnings'].append("Key uses only one case. Consider mixed case for better entropy.")
        
        if any(weak in key.lower() for weak in ['password', 'secret', 'key', '123', 'abc']):
            results['warnings'].append("Key contains common weak patterns.")
        
        # Overall validation
        results['valid'] = results['meets_minimum'] and len(results['warnings']) == 0
        
        return results
    
    @classmethod
    def generate_multiple_keys(cls) -> dict:
        """Generate multiple keys using different methods for comparison"""
        return {
            'urlsafe_32': cls.generate_urlsafe_key(32),
            'urlsafe_64': cls.generate_urlsafe_key(64),
            'hex_32': cls.generate_hex_key(32),
            'hex_64': cls.generate_hex_key(64),
            'bytes_32': cls.generate_bytes_key(32),
            'bytes_64': cls.generate_bytes_key(64)
        }

def interactive_key_generation():
    """Interactive key generation with user choices"""
    print("🔐 HomeChef Companion Secret Key Generator")
    print("=" * 50)
    
    print("\nAvailable key generation methods:")
    print("1. URL-safe (Recommended for FastAPI)")
    print("2. Hexadecimal")
    print("3. Base64 encoded bytes")
    print("4. Generate multiple keys for comparison")
    print("5. Validate existing key")
    
    while True:
        try:
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == "1":
                length = input(f"Key length in bytes (default {SecretKeyGenerator.RECOMMENDED_LENGTH}): ").strip()
                length = int(length) if length else SecretKeyGenerator.RECOMMENDED_LENGTH
                key = SecretKeyGenerator.generate_urlsafe_key(length)
                print(f"\n🔑 Generated URL-safe key:")
                print(f"SECRET_KEY={key}")
                return key
                
            elif choice == "2":
                length = input(f"Key length in bytes (default {SecretKeyGenerator.RECOMMENDED_LENGTH}): ").strip()
                length = int(length) if length else SecretKeyGenerator.RECOMMENDED_LENGTH
                key = SecretKeyGenerator.generate_hex_key(length)
                print(f"\n🔑 Generated hex key:")
                print(f"SECRET_KEY={key}")
                return key
                
            elif choice == "3":
                length = input(f"Key length in bytes (default {SecretKeyGenerator.RECOMMENDED_LENGTH}): ").strip()
                length = int(length) if length else SecretKeyGenerator.RECOMMENDED_LENGTH
                key = SecretKeyGenerator.generate_bytes_key(length)
                print(f"\n🔑 Generated base64 key:")
                print(f"SECRET_KEY={key}")
                return key
                
            elif choice == "4":
                keys = SecretKeyGenerator.generate_multiple_keys()
                print(f"\n🔑 Generated multiple keys:")
                for method, key in keys.items():
                    print(f"{method:12}: {key}")
                
                selected = input("\nWhich key would you like to use? (urlsafe_64 recommended): ").strip()
                if selected in keys:
                    return keys[selected]
                else:
                    print("Invalid selection, using urlsafe_64")
                    return keys['urlsafe_64']
                    
            elif choice == "5":
                existing_key = input("Enter your existing key to validate: ").strip()
                if existing_key:
                    validation = SecretKeyGenerator.validate_key_strength(existing_key)
                    print(f"\n📊 Key Validation Results:")
                    print(f"Length: {validation['length_bytes']} bytes ({validation['length_bits']} bits)")
                    print(f"Meets minimum requirements: {'✅' if validation['meets_minimum'] else '❌'}")
                    print(f"Recommended strength: {'✅' if validation['recommended_strength'] else '⚠️'}")
                    
                    if validation['warnings']:
                        print(f"\n⚠️ Warnings:")
                        for warning in validation['warnings']:
                            print(f"  - {warning}")
                    
                    if validation['valid']:
                        print(f"\n✅ Key is valid and secure!")
                    else:
                        print(f"\n❌ Key needs improvement.")
                continue
                
            else:
                print("Invalid choice. Please select 1-5.")
                continue
                
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\n\nExiting...")
            sys.exit(0)

def main():
    """Main function for command line usage"""
    if len(sys.argv) > 1:
        # Command line mode
        method = sys.argv[1].lower()
        length = int(sys.argv[2]) if len(sys.argv) > 2 else SecretKeyGenerator.RECOMMENDED_LENGTH
        
        if method == "urlsafe":
            key = SecretKeyGenerator.generate_urlsafe_key(length)
        elif method == "hex":
            key = SecretKeyGenerator.generate_hex_key(length)
        elif method == "bytes":
            key = SecretKeyGenerator.generate_bytes_key(length)
        else:
            print(f"Unknown method: {method}")
            print("Available methods: urlsafe, hex, bytes")
            sys.exit(1)
        
        print(key)
    else:
        # Interactive mode
        interactive_key_generation()

if __name__ == "__main__":
    main()