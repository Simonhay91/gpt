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
        elif status == 400 and 'already registered' in str(data):
            self.log_test("User Registration - Regular user", True, 
                         "User already exists (expected in testing environment)")
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
        elif status == 400 and 'already registered' in str(data):
            self.log_test("User Registration - Admin user", True, 
                         "Admin user already exists (expected in testing environment)")
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

    def test_source_file_operations(self):
        """Test file source upload (PDF, DOCX, TXT, MD), list, and delete operations"""
        if not self.test_user_token or not self.test_project_id:
            self.log_test("Source Files - Missing requirements", False, 
                         "No test user token or project ID available")
            return

        # Create a proper PDF with extractable text content
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
/Resources <<
/Font <<
/F1 5 0 R
>>
>>
>>
endobj

4 0 obj
<<
/Length 85
>>
stream
BT
/F1 12 Tf
72 720 Td
(This is a test PDF document with extractable text content.) Tj
0 -20 Td
(It contains multiple lines of text for testing purposes.) Tj
ET
endstream
endobj

5 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj

xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000273 00000 n 
0000000408 00000 n 
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
486
%%EOF"""

        # Test PDF upload
        url = f"{self.api_url}/projects/{self.test_project_id}/sources/upload"
        headers = {'Authorization': f'Bearer {self.test_user_token}'}
        files = {'file': ('test.pdf', pdf_content, 'application/pdf')}
        
        try:
            response = requests.post(url, files=files, headers=headers, timeout=30)
            success = response.status_code == 200
            data = response.json() if success else {"error": response.text}
            
            if success and 'id' in data:
                self.test_file_id = data['id']
                self.log_test("Source Files - PDF Upload", True, 
                             f"Source ID: {self.test_file_id}, Chunks: {data.get('chunkCount', 0)}")
            else:
                self.log_test("Source Files - PDF Upload", False, 
                             f"Status: {response.status_code}, Data: {data}")
                return
                
        except Exception as e:
            self.log_test("Source Files - PDF Upload", False, f"Error: {str(e)}")
            return

        # Test TXT file upload
        txt_content = "This is a test text document.\nIt contains multiple lines of text for testing purposes.\nThis should be chunked properly."
        files = {'file': ('test.txt', txt_content.encode('utf-8'), 'text/plain')}
        
        try:
            response = requests.post(url, files=files, headers=headers, timeout=30)
            success = response.status_code == 200
            data = response.json() if success else {"error": response.text}
            
            if success and 'id' in data:
                self.log_test("Source Files - TXT Upload", True, 
                             f"Source ID: {data['id']}, Chunks: {data.get('chunkCount', 0)}")
            else:
                self.log_test("Source Files - TXT Upload", False, 
                             f"Status: {response.status_code}, Data: {data}")
                
        except Exception as e:
            self.log_test("Source Files - TXT Upload", False, f"Error: {str(e)}")

        # Test MD file upload
        md_content = "# Test Markdown Document\n\nThis is a **test** markdown document.\n\n## Section 1\n\nIt contains multiple sections for testing purposes."
        files = {'file': ('test.md', md_content.encode('utf-8'), 'text/markdown')}
        
        try:
            response = requests.post(url, files=files, headers=headers, timeout=30)
            success = response.status_code == 200
            data = response.json() if success else {"error": response.text}
            
            if success and 'id' in data:
                self.log_test("Source Files - MD Upload", True, 
                             f"Source ID: {data['id']}, Chunks: {data.get('chunkCount', 0)}")
            else:
                self.log_test("Source Files - MD Upload", False, 
                             f"Status: {response.status_code}, Data: {data}")
                
        except Exception as e:
            self.log_test("Source Files - MD Upload", False, f"Error: {str(e)}")

        # Test list sources
        success, data, status = self.make_request('GET', f'/projects/{self.test_project_id}/sources', 
                                                 token=self.test_user_token)
        
        if success and status == 200 and isinstance(data, list):
            file_found = any(f['id'] == self.test_file_id for f in data)
            self.log_test("Source Files - List", file_found and len(data) >= 1, 
                         f"Found {len(data)} sources, test PDF found: {file_found}")
        else:
            self.log_test("Source Files - List", False, f"Status: {status}, Data: {data}")

        # Test unsupported file upload (should fail)
        files = {'file': ('test.exe', b'This is not a supported file', 'application/octet-stream')}
        
        try:
            response = requests.post(url, files=files, headers=headers, timeout=30)
            self.log_test("Source Files - Unsupported file rejection", response.status_code == 400, 
                         f"Status: {response.status_code} (should be 400)")
        except Exception as e:
            self.log_test("Source Files - Unsupported file rejection", False, f"Error: {str(e)}")

    def test_url_source_operations(self):
        """Test URL source operations"""
        if not self.test_user_token or not self.test_project_id:
            self.log_test("URL Sources - Missing requirements", False, 
                         "No test user token or project ID available")
            return

        # Test valid URL addition
        test_url = "https://httpbin.org/html"
        success, data, status = self.make_request('POST', f'/projects/{self.test_project_id}/sources/url', {
            "url": test_url
        }, token=self.test_user_token)
        
        if success and status == 200 and 'id' in data:
            self.test_url_source_id = data['id']
            self.log_test("URL Sources - Add valid URL", True, 
                         f"Source ID: {self.test_url_source_id}, Chunks: {data.get('chunkCount', 0)}")
        else:
            self.log_test("URL Sources - Add valid URL", False, 
                         f"Status: {status}, Data: {data}")

        # Test invalid URL (should fail)
        success, data, status = self.make_request('POST', f'/projects/{self.test_project_id}/sources/url', {
            "url": "not-a-valid-url"
        }, token=self.test_user_token)
        
        self.log_test("URL Sources - Invalid URL rejection", status == 400, 
                     f"Status: {status} (should be 400)")

        # Test non-existent URL (should fail)
        success, data, status = self.make_request('POST', f'/projects/{self.test_project_id}/sources/url', {
            "url": "https://this-domain-does-not-exist-12345.com"
        }, token=self.test_user_token)
        
        self.log_test("URL Sources - Non-existent URL rejection", status == 400, 
                     f"Status: {status} (should be 400)")

    def test_active_sources_operations(self):
        """Test setting and getting active sources for chats"""
        if not self.test_user_token or not self.test_chat_id:
            self.log_test("Active Sources - Missing requirements", False, 
                         "Missing token or chat ID")
            return
            
        if not hasattr(self, 'test_file_id') or not self.test_file_id:
            self.log_test("Active Sources - No source ID", False, 
                         "No test source ID available (source upload may have failed)")
            return

        # Test set active sources
        success, data, status = self.make_request('POST', f'/chats/{self.test_chat_id}/active-sources', {
            "sourceIds": [self.test_file_id]
        }, token=self.test_user_token)
        
        if success and status == 200:
            self.log_test("Active Sources - Set active", True, 
                         f"Active sources set: {data.get('activeSourceIds', [])}")
        else:
            self.log_test("Active Sources - Set active", False, f"Status: {status}, Data: {data}")

        # Test get active sources
        success, data, status = self.make_request('GET', f'/chats/{self.test_chat_id}/active-sources', 
                                                 token=self.test_user_token)
        
        if success and status == 200 and 'activeSources' in data:
            active_sources = data['activeSources']
            source_found = any(s['id'] == self.test_file_id for s in active_sources)
            self.log_test("Active Sources - Get active", source_found, 
                         f"Found {len(active_sources)} active sources, test source found: {source_found}")
        else:
            self.log_test("Active Sources - Get active", False, f"Status: {status}, Data: {data}")

        # Test invalid source ID (should fail)
        success, data, status = self.make_request('POST', f'/chats/{self.test_chat_id}/active-sources', {
            "sourceIds": ["invalid-source-id"]
        }, token=self.test_user_token)
        
        self.log_test("Active Sources - Invalid source ID", status == 400, 
                     f"Status: {status} (should be 400)")

    def test_message_with_source_context(self):
        """Test sending messages with source context and citations"""
        if not self.test_user_token or not self.test_chat_id:
            self.log_test("Message with Context - Missing requirements", False, 
                         "Missing token or chat ID")
            return

        # Send a message that should use the source context
        success, data, status = self.make_request('POST', f'/chats/{self.test_chat_id}/messages', {
            "content": "What does the document say about testing?"
        }, token=self.test_user_token)
        
        if success and status == 200 and 'content' in data:
            # Check if the response seems to reference document content
            response_content = data['content'].lower()
            has_context_reference = any(word in response_content for word in 
                                      ['document', 'pdf', 'file', 'content', 'text', 'testing'])
            
            # Check for citations
            has_citations = data.get('citations') is not None and len(data.get('citations', [])) > 0
            
            self.log_test("Message with Context - AI uses source context", has_context_reference, 
                         f"AI Response: {data['content'][:100]}...")
            
            self.log_test("Message with Context - Citations present", has_citations, 
                         f"Citations: {data.get('citations', [])}")
        else:
            self.log_test("Message with Context - AI uses source context", False, 
                         f"Status: {status}, Data: {data}")
            self.log_test("Message with Context - Citations present", False, 
                         f"Status: {status}, Data: {data}")

    def test_project_source_isolation(self):
        """Test that sources are isolated between projects"""
        if not self.test_user_token or not hasattr(self, 'test_file_id'):
            self.log_test("Source Isolation - Missing requirements", False, 
                         "Missing token or source ID")
            return

        # Create a second project
        success, data, status = self.make_request('POST', '/projects', {
            "name": "Second Test Project"
        }, token=self.test_user_token)
        
        if success and status == 200 and 'id' in data:
            second_project_id = data['id']
            
            # Try to access the source from the first project via the second project (should fail)
            success, data, status = self.make_request('GET', f'/projects/{second_project_id}/sources', 
                                                     token=self.test_user_token)
            
            if success and status == 200 and isinstance(data, list):
                source_found = any(s['id'] == self.test_file_id for s in data)
                self.log_test("Source Isolation - Cross-project access", not source_found, 
                             f"Source found in wrong project: {source_found} (should be False)")
            else:
                self.log_test("Source Isolation - Cross-project access", False, 
                             f"Status: {status}, Data: {data}")
            
            # Cleanup second project
            self.make_request('DELETE', f'/projects/{second_project_id}', token=self.test_user_token)
        else:
            self.log_test("Source Isolation - Create second project", False, 
                         f"Status: {status}, Data: {data}")

    def test_source_deletion(self):
        """Test source deletion functionality"""
        if not self.test_user_token or not self.test_project_id or not hasattr(self, 'test_file_id'):
            self.log_test("Source Deletion - Missing requirements", False, 
                         "Missing token, project ID, or source ID")
            return

        # Delete the test source
        success, data, status = self.make_request('DELETE', f'/projects/{self.test_project_id}/sources/{self.test_file_id}', 
                                                 token=self.test_user_token)
        
        if success and status == 200:
            self.log_test("Source Deletion - Delete source", True, "Source deleted successfully")
            
            # Verify source is no longer in the list
            success, data, status = self.make_request('GET', f'/projects/{self.test_project_id}/sources', 
                                                     token=self.test_user_token)
            
            if success and status == 200 and isinstance(data, list):
                source_found = any(s['id'] == self.test_file_id for s in data)
                self.log_test("Source Deletion - Verify deletion", not source_found, 
                             f"Source still found after deletion: {source_found} (should be False)")
            else:
                self.log_test("Source Deletion - Verify deletion", False, 
                             f"Status: {status}, Data: {data}")
        else:
            self.log_test("Source Deletion - Delete source", False, 
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
        if hasattr(self, 'test_file_id') and self.test_file_id and self.test_user_token and self.test_project_id:
            success, data, status = self.make_request('DELETE', f'/projects/{self.test_project_id}/files/{self.test_file_id}', 
                                                     token=self.test_user_token)
            print(f"🧹 Cleanup file: {'✅' if success else '❌'}")

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
            
            # PDF file operations
            self.test_pdf_file_operations()
            self.test_active_files_operations()
            self.test_message_with_file_context()
            
            # Admin functionality
            self.test_admin_config()
            
            # Security tests
            self.test_project_isolation()
            self.test_project_file_isolation()
            
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