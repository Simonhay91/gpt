#!/usr/bin/env python3
"""
Backend API Testing for Shared Project GPT
Tests all CRUD operations, authentication, and admin functionality
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class SharedProjectGPTTester:
    def __init__(self, base_url: str = "https://multi-tenant-gpt.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.test_user_token = None
        self.admin_user_token = None
        self.test_user_id = None
        self.admin_user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Test data
        self.test_user_email = "test@example.com"
        self.test_user_password = "test123"
        self.admin_user_email = "admin@admin.com"
        self.admin_user_password = "admin123"
        
        # Test entities
        self.test_project_id = None
        self.test_chat_id = None
        self.test_file_id = None

    def log_test(self, name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details,
            "response_data": response_data
        })

    def make_request(self, method: str, endpoint: str, data: Dict = None, token: str = None) -> tuple:
        """Make HTTP request and return (success, response_data, status_code)"""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        headers = {'Content-Type': 'application/json'}
        
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return False, {"error": f"Unsupported method: {method}"}, 0
            
            try:
                response_data = response.json()
            except:
                response_data = {"text": response.text}
            
            return response.status_code < 400, response_data, response.status_code
            
        except Exception as e:
            return False, {"error": str(e)}, 0

    def test_health_check(self):
        """Test basic health endpoints"""
        success, data, status = self.make_request('GET', '/')
        self.log_test("Health Check - Root", success and status == 200, 
                     f"Status: {status}, Data: {data}")
        
        success, data, status = self.make_request('GET', '/health')
        self.log_test("Health Check - Health endpoint", success and status == 200,
                     f"Status: {status}, Data: {data}")

    def test_user_registration(self):
        """Test user registration"""
        # Test regular user registration
        success, data, status = self.make_request('POST', '/auth/register', {
            "email": self.test_user_email,
            "password": self.test_user_password
        })
        
        if success and status == 200 and 'token' in data:
            self.test_user_token = data['token']
            self.test_user_id = data['user']['id']
            self.log_test("User Registration - Regular user", True, 
                         f"User ID: {self.test_user_id}, isAdmin: {data['user']['isAdmin']}")
        else:
            self.log_test("User Registration - Regular user", False, 
                         f"Status: {status}, Data: {data}")

        # Test admin user registration
        success, data, status = self.make_request('POST', '/auth/register', {
            "email": self.admin_user_email,
            "password": self.admin_user_password
        })
        
        if success and status == 200 and 'token' in data:
            self.admin_user_token = data['token']
            self.admin_user_id = data['user']['id']
            is_admin = data['user']['isAdmin']
            self.log_test("User Registration - Admin user", is_admin, 
                         f"User ID: {self.admin_user_id}, isAdmin: {is_admin}")
        else:
            self.log_test("User Registration - Admin user", False, 
                         f"Status: {status}, Data: {data}")

    def test_user_login(self):
        """Test user login"""
        # Test regular user login
        success, data, status = self.make_request('POST', '/auth/login', {
            "email": self.test_user_email,
            "password": self.test_user_password
        })
        
        if success and status == 200 and 'token' in data:
            self.test_user_token = data['token']
            self.log_test("User Login - Regular user", True, f"Token received")
        else:
            self.log_test("User Login - Regular user", False, 
                         f"Status: {status}, Data: {data}")

        # Test admin user login
        success, data, status = self.make_request('POST', '/auth/login', {
            "email": self.admin_user_email,
            "password": self.admin_user_password
        })
        
        if success and status == 200 and 'token' in data:
            self.admin_user_token = data['token']
            self.log_test("User Login - Admin user", True, f"Token received")
        else:
            self.log_test("User Login - Admin user", False, 
                         f"Status: {status}, Data: {data}")

        # Test invalid credentials
        success, data, status = self.make_request('POST', '/auth/login', {
            "email": "invalid@example.com",
            "password": "wrongpassword"
        })
        
        self.log_test("User Login - Invalid credentials", status == 401, 
                     f"Status: {status} (should be 401)")

    def test_auth_me(self):
        """Test /auth/me endpoint"""
        if not self.test_user_token:
            self.log_test("Auth Me - No token", False, "No test user token available")
            return
        
        success, data, status = self.make_request('GET', '/auth/me', token=self.test_user_token)
        
        if success and status == 200 and 'email' in data:
            self.log_test("Auth Me - Valid token", True, 
                         f"Email: {data['email']}, isAdmin: {data.get('isAdmin', False)}")
        else:
            self.log_test("Auth Me - Valid token", False, 
                         f"Status: {status}, Data: {data}")

    def test_projects_crud(self):
        """Test project CRUD operations"""
        if not self.test_user_token:
            self.log_test("Projects CRUD - No token", False, "No test user token available")
            return

        # Test create project
        success, data, status = self.make_request('POST', '/projects', {
            "name": "Test Project"
        }, token=self.test_user_token)
        
        if success and status == 200 and 'id' in data:
            self.test_project_id = data['id']
            self.log_test("Projects - Create", True, f"Project ID: {self.test_project_id}")
        else:
            self.log_test("Projects - Create", False, f"Status: {status}, Data: {data}")
            return

        # Test get projects list
        success, data, status = self.make_request('GET', '/projects', token=self.test_user_token)
        
        if success and status == 200 and isinstance(data, list):
            project_found = any(p['id'] == self.test_project_id for p in data)
            self.log_test("Projects - List", project_found, 
                         f"Found {len(data)} projects, test project found: {project_found}")
        else:
            self.log_test("Projects - List", False, f"Status: {status}, Data: {data}")

        # Test get specific project
        success, data, status = self.make_request('GET', f'/projects/{self.test_project_id}', 
                                                 token=self.test_user_token)
        
        if success and status == 200 and data.get('id') == self.test_project_id:
            self.log_test("Projects - Get by ID", True, f"Project name: {data.get('name')}")
        else:
            self.log_test("Projects - Get by ID", False, f"Status: {status}, Data: {data}")

    def test_chats_crud(self):
        """Test chat CRUD operations"""
        if not self.test_user_token or not self.test_project_id:
            self.log_test("Chats CRUD - Missing requirements", False, 
                         "No test user token or project ID available")
            return

        # Test create chat
        success, data, status = self.make_request('POST', f'/projects/{self.test_project_id}/chats', {
            "name": "Test Chat"
        }, token=self.test_user_token)
        
        if success and status == 200 and 'id' in data:
            self.test_chat_id = data['id']
            self.log_test("Chats - Create", True, f"Chat ID: {self.test_chat_id}")
        else:
            self.log_test("Chats - Create", False, f"Status: {status}, Data: {data}")
            return

        # Test get chats list
        success, data, status = self.make_request('GET', f'/projects/{self.test_project_id}/chats', 
                                                 token=self.test_user_token)
        
        if success and status == 200 and isinstance(data, list):
            chat_found = any(c['id'] == self.test_chat_id for c in data)
            self.log_test("Chats - List", chat_found, 
                         f"Found {len(data)} chats, test chat found: {chat_found}")
        else:
            self.log_test("Chats - List", False, f"Status: {status}, Data: {data}")

    def test_messages_crud(self):
        """Test message CRUD operations"""
        if not self.test_user_token or not self.test_chat_id:
            self.log_test("Messages CRUD - Missing requirements", False, 
                         "No test user token or chat ID available")
            return

        # Test get messages (should be empty initially)
        success, data, status = self.make_request('GET', f'/chats/{self.test_chat_id}/messages', 
                                                 token=self.test_user_token)
        
        if success and status == 200 and isinstance(data, list):
            self.log_test("Messages - Get empty list", len(data) == 0, 
                         f"Found {len(data)} messages (should be 0)")
        else:
            self.log_test("Messages - Get empty list", False, f"Status: {status}, Data: {data}")

        # Test send message (this will also test AI integration)
        success, data, status = self.make_request('POST', f'/chats/{self.test_chat_id}/messages', {
            "content": "Hello, this is a test message"
        }, token=self.test_user_token)
        
        if success and status == 200 and 'content' in data:
            self.log_test("Messages - Send message", True, 
                         f"AI Response: {data['content'][:100]}...")
        else:
            self.log_test("Messages - Send message", False, f"Status: {status}, Data: {data}")

        # Test get messages after sending
        success, data, status = self.make_request('GET', f'/chats/{self.test_chat_id}/messages', 
                                                 token=self.test_user_token)
        
        if success and status == 200 and isinstance(data, list):
            # Should have user message + AI response
            self.log_test("Messages - Get after sending", len(data) >= 2, 
                         f"Found {len(data)} messages (should be >= 2)")
        else:
            self.log_test("Messages - Get after sending", False, f"Status: {status}, Data: {data}")

    def test_admin_config(self):
        """Test admin configuration endpoints"""
        if not self.admin_user_token:
            self.log_test("Admin Config - No admin token", False, "No admin user token available")
            return

        # Test get config with admin user
        success, data, status = self.make_request('GET', '/admin/config', 
                                                 token=self.admin_user_token)
        
        if success and status == 200 and 'model' in data:
            self.log_test("Admin Config - Get config", True, 
                         f"Model: {data['model']}, Prompt length: {len(data.get('developerPrompt', ''))}")
        else:
            self.log_test("Admin Config - Get config", False, f"Status: {status}, Data: {data}")

        # Test update config
        success, data, status = self.make_request('PUT', '/admin/config', {
            "model": "gpt-4.1-mini",
            "developerPrompt": "You are a helpful test assistant."
        }, token=self.admin_user_token)
        
        if success and status == 200:
            self.log_test("Admin Config - Update config", True, "Config updated successfully")
        else:
            self.log_test("Admin Config - Update config", False, f"Status: {status}, Data: {data}")

        # Test access with regular user (should fail)
        if self.test_user_token:
            success, data, status = self.make_request('GET', '/admin/config', 
                                                     token=self.test_user_token)
            
            self.log_test("Admin Config - Regular user access", status == 403, 
                         f"Status: {status} (should be 403)")

    def test_pdf_file_operations(self):
        """Test PDF file upload, list, and delete operations"""
        if not self.test_user_token or not self.test_project_id:
            self.log_test("PDF Files - Missing requirements", False, 
                         "No test user token or project ID available")
            return

        # Create a simple PDF content for testing (minimal PDF structure)
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Test PDF content) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000204 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
297
%%EOF"""

        # Test file upload
        url = f"{self.api_url}/projects/{self.test_project_id}/files"
        headers = {'Authorization': f'Bearer {self.test_user_token}'}
        files = {'file': ('test.pdf', pdf_content, 'application/pdf')}
        
        try:
            response = requests.post(url, files=files, headers=headers, timeout=30)
            success = response.status_code == 200
            data = response.json() if success else {"error": response.text}
            
            if success and 'id' in data:
                self.test_file_id = data['id']
                self.log_test("PDF Files - Upload", True, 
                             f"File ID: {self.test_file_id}, Chunks: {data.get('chunkCount', 0)}")
            else:
                self.log_test("PDF Files - Upload", False, 
                             f"Status: {response.status_code}, Data: {data}")
                return
                
        except Exception as e:
            self.log_test("PDF Files - Upload", False, f"Error: {str(e)}")
            return

        # Test list files
        success, data, status = self.make_request('GET', f'/projects/{self.test_project_id}/files', 
                                                 token=self.test_user_token)
        
        if success and status == 200 and isinstance(data, list):
            file_found = any(f['id'] == self.test_file_id for f in data)
            self.log_test("PDF Files - List", file_found, 
                         f"Found {len(data)} files, test file found: {file_found}")
        else:
            self.log_test("PDF Files - List", False, f"Status: {status}, Data: {data}")

        # Test non-PDF file upload (should fail)
        url = f"{self.api_url}/projects/{self.test_project_id}/files"
        files = {'file': ('test.txt', b'This is not a PDF', 'text/plain')}
        
        try:
            response = requests.post(url, files=files, headers=headers, timeout=30)
            self.log_test("PDF Files - Non-PDF rejection", response.status_code == 400, 
                         f"Status: {response.status_code} (should be 400)")
        except Exception as e:
            self.log_test("PDF Files - Non-PDF rejection", False, f"Error: {str(e)}")

    def test_active_files_operations(self):
        """Test setting and getting active files for chats"""
        if not self.test_user_token or not self.test_chat_id or not hasattr(self, 'test_file_id'):
            self.log_test("Active Files - Missing requirements", False, 
                         "Missing token, chat ID, or file ID")
            return

        # Test set active files
        success, data, status = self.make_request('POST', f'/chats/{self.test_chat_id}/active-files', {
            "fileIds": [self.test_file_id]
        }, token=self.test_user_token)
        
        if success and status == 200:
            self.log_test("Active Files - Set active", True, 
                         f"Active files set: {data.get('activeFileIds', [])}")
        else:
            self.log_test("Active Files - Set active", False, f"Status: {status}, Data: {data}")

        # Test get active files
        success, data, status = self.make_request('GET', f'/chats/{self.test_chat_id}/active-files', 
                                                 token=self.test_user_token)
        
        if success and status == 200 and 'activeFiles' in data:
            active_files = data['activeFiles']
            file_found = any(f['id'] == self.test_file_id for f in active_files)
            self.log_test("Active Files - Get active", file_found, 
                         f"Found {len(active_files)} active files, test file found: {file_found}")
        else:
            self.log_test("Active Files - Get active", False, f"Status: {status}, Data: {data}")

        # Test invalid file ID (should fail)
        success, data, status = self.make_request('POST', f'/chats/{self.test_chat_id}/active-files', {
            "fileIds": ["invalid-file-id"]
        }, token=self.test_user_token)
        
        self.log_test("Active Files - Invalid file ID", status == 400, 
                     f"Status: {status} (should be 400)")

    def test_message_with_file_context(self):
        """Test sending messages with file context"""
        if not self.test_user_token or not self.test_chat_id:
            self.log_test("Message with Context - Missing requirements", False, 
                         "Missing token or chat ID")
            return

        # Send a message that should use the PDF context
        success, data, status = self.make_request('POST', f'/chats/{self.test_chat_id}/messages', {
            "content": "What does the document say?"
        }, token=self.test_user_token)
        
        if success and status == 200 and 'content' in data:
            # Check if the response seems to reference document content
            response_content = data['content'].lower()
            has_context_reference = any(word in response_content for word in 
                                      ['document', 'pdf', 'file', 'content', 'text'])
            self.log_test("Message with Context - AI uses file context", has_context_reference, 
                         f"AI Response: {data['content'][:100]}...")
        else:
            self.log_test("Message with Context - AI uses file context", False, 
                         f"Status: {status}, Data: {data}")

    def test_project_file_isolation(self):
        """Test that files are isolated between projects"""
        if not self.test_user_token or not hasattr(self, 'test_file_id'):
            self.log_test("File Isolation - Missing requirements", False, 
                         "Missing token or file ID")
            return

        # Create a second project
        success, data, status = self.make_request('POST', '/projects', {
            "name": "Second Test Project"
        }, token=self.test_user_token)
        
        if success and status == 200 and 'id' in data:
            second_project_id = data['id']
            
            # Try to access the file from the first project via the second project (should fail)
            success, data, status = self.make_request('GET', f'/projects/{second_project_id}/files', 
                                                     token=self.test_user_token)
            
            if success and status == 200 and isinstance(data, list):
                file_found = any(f['id'] == self.test_file_id for f in data)
                self.log_test("File Isolation - Cross-project access", not file_found, 
                             f"File found in wrong project: {file_found} (should be False)")
            else:
                self.log_test("File Isolation - Cross-project access", False, 
                             f"Status: {status}, Data: {data}")
            
            # Cleanup second project
            self.make_request('DELETE', f'/projects/{second_project_id}', token=self.test_user_token)
        else:
            self.log_test("File Isolation - Create second project", False, 
                         f"Status: {status}, Data: {data}")

    def test_project_isolation(self):
        """Test that users can't access each other's projects"""
        if not self.test_user_token or not self.admin_user_token or not self.test_project_id:
            self.log_test("Project Isolation - Missing requirements", False, 
                         "Missing tokens or project ID")
            return

        # Try to access test user's project with admin token (should fail)
        success, data, status = self.make_request('GET', f'/projects/{self.test_project_id}', 
                                                 token=self.admin_user_token)
        
        self.log_test("Project Isolation - Cross-user access", status == 404, 
                     f"Status: {status} (should be 404)")

    def cleanup_test_data(self):
        """Clean up test data"""
        if self.test_chat_id and self.test_user_token:
            success, data, status = self.make_request('DELETE', f'/chats/{self.test_chat_id}', 
                                                     token=self.test_user_token)
            print(f"🧹 Cleanup chat: {'✅' if success else '❌'}")

        if self.test_project_id and self.test_user_token:
            success, data, status = self.make_request('DELETE', f'/projects/{self.test_project_id}', 
                                                     token=self.test_user_token)
            print(f"🧹 Cleanup project: {'✅' if success else '❌'}")

    def run_all_tests(self):
        """Run all tests in sequence"""
        print(f"🚀 Starting Shared Project GPT Backend Tests")
        print(f"📍 Base URL: {self.base_url}")
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        try:
            # Basic health checks
            self.test_health_check()
            
            # Authentication tests
            self.test_user_registration()
            self.test_user_login()
            self.test_auth_me()
            
            # CRUD operations
            self.test_projects_crud()
            self.test_chats_crud()
            self.test_messages_crud()
            
            # Admin functionality
            self.test_admin_config()
            
            # Security tests
            self.test_project_isolation()
            
        except Exception as e:
            print(f"❌ Test suite failed with error: {str(e)}")
        
        finally:
            # Cleanup
            self.cleanup_test_data()
            
            # Print summary
            print("=" * 60)
            print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
            print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            if self.tests_passed == self.tests_run:
                print("🎉 All tests passed!")
                return 0
            else:
                print("⚠️  Some tests failed!")
                return 1

def main():
    tester = SharedProjectGPTTester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())