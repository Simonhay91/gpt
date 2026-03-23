#!/usr/bin/env python3
"""
Brave Search Integration Testing for Planet Knowledge API
Tests the Brave Search functionality in messages.py
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class BraveSearchTester:
    def __init__(self, base_url: str = "https://spreadsheet-ai-3.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.admin_token = None
        self.admin_user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Admin credentials
        self.admin_email = "admin@ai.planetworkspace.com"
        self.admin_password = "Admin@123456"

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

    def login_admin(self):
        """Login as admin user"""
        success, data, status = self.make_request('POST', '/auth/login', {
            "email": self.admin_email,
            "password": self.admin_password
        })
        
        if success and status == 200 and 'token' in data:
            self.admin_token = data['token']
            self.admin_user_id = data['user']['id']
            self.log_test("Admin Login", True, f"User ID: {self.admin_user_id}")
            return True
        else:
            self.log_test("Admin Login", False, f"Status: {status}, Data: {data}")
            return False

    def get_or_create_chat(self):
        """Get existing quick chat or create new one"""
        success, data, status = self.make_request('GET', '/quick-chats', token=self.admin_token)
        
        if success and status == 200 and isinstance(data, list) and len(data) > 0:
            chat_id = data[0]['id']
            self.log_test("Use Existing Quick Chat", True, f"Chat ID: {chat_id}")
            return chat_id
        else:
            # Create a quick chat
            success, data, status = self.make_request('POST', '/quick-chats', {
                "name": "Brave Search Test Chat"
            }, token=self.admin_token)
            
            if success and status == 200 and 'id' in data:
                chat_id = data['id']
                self.log_test("Create Quick Chat", True, f"Chat ID: {chat_id}")
                return chat_id
            else:
                self.log_test("Create Quick Chat", False, f"Status: {status}, Data: {data}")
                return None

    def test_russian_research_keyword(self, chat_id: str):
        """Test message with Russian research keyword"""
        message = "найди в интернете информацию про Python programming"
        
        success, data, status = self.make_request('POST', f'/chats/{chat_id}/messages', {
            "content": message
        }, token=self.admin_token)
        
        if success and status == 200:
            # Check for web_sources field
            has_web_sources = 'web_sources' in data and data.get('web_sources') is not None
            web_sources = data.get('web_sources', [])
            
            self.log_test("Russian Keyword Triggers Web Search", has_web_sources,
                         f"web_sources present: {has_web_sources}, Count: {len(web_sources)}")
            
            if has_web_sources and web_sources:
                print(f"   🌐 Web Sources Found: {len(web_sources)} results")
                for i, source in enumerate(web_sources[:3]):
                    print(f"      {i+1}. {source.get('title', 'No title')} - {source.get('url', 'No URL')}")
            
            # Check AI response content
            response_content = data.get('content', '')
            has_web_references = any(keyword in response_content.lower() for keyword in 
                                   ['web', 'search', 'found', 'results', 'ссылки', 'источник'])
            
            self.log_test("Russian - AI Response Includes Web Results", has_web_references,
                         f"Response contains web references: {has_web_references}")
            
            print(f"   📝 AI Response Preview: {response_content[:200]}...")
            return True
            
        else:
            self.log_test("Russian Keyword Triggers Web Search", False,
                         f"Message failed: Status {status}, Data: {data}")
            return False

    def test_english_research_keyword(self, chat_id: str):
        """Test message with English research keyword"""
        message = "research latest AI trends"
        
        success, data, status = self.make_request('POST', f'/chats/{chat_id}/messages', {
            "content": message
        }, token=self.admin_token)
        
        if success and status == 200:
            # Check for web_sources field
            has_web_sources = 'web_sources' in data and data.get('web_sources') is not None
            web_sources = data.get('web_sources', [])
            
            self.log_test("English Keyword Triggers Web Search", has_web_sources,
                         f"web_sources present: {has_web_sources}, Count: {len(web_sources)}")
            
            if has_web_sources and web_sources:
                print(f"   🌐 Web Sources Found: {len(web_sources)} results")
                for i, source in enumerate(web_sources[:3]):
                    print(f"      {i+1}. {source.get('title', 'No title')} - {source.get('url', 'No URL')}")
            
            # Check AI response content
            response_content = data.get('content', '')
            has_web_references = any(keyword in response_content.lower() for keyword in 
                                   ['web', 'search', 'found', 'results', 'links', 'sources'])
            
            self.log_test("English - AI Response Includes Web Results", has_web_references,
                         f"Response contains web references: {has_web_references}")
            
            print(f"   📝 AI Response Preview: {response_content[:200]}...")
            return True
            
        else:
            self.log_test("English Keyword Triggers Web Search", False,
                         f"Message failed: Status {status}, Data: {data}")
            return False

    def test_normal_message_no_web_search(self, chat_id: str):
        """Test normal message without research keywords (should use RAG)"""
        message = "What is Python programming?"
        
        success, data, status = self.make_request('POST', f'/chats/{chat_id}/messages', {
            "content": message
        }, token=self.admin_token)
        
        if success and status == 200:
            # Should NOT have web_sources for normal messages
            has_web_sources = 'web_sources' in data and data.get('web_sources') is not None
            web_sources = data.get('web_sources', [])
            
            self.log_test("Normal Message Uses RAG (No Web Search)", not has_web_sources,
                         f"web_sources should be None: {has_web_sources}, Sources: {len(web_sources) if web_sources else 0}")
            
            # Check for regular RAG citations
            has_citations = 'citations' in data and data.get('citations') is not None
            citations = data.get('citations', [])
            
            self.log_test("Normal Message Has RAG Citations", has_citations,
                         f"Citations present: {has_citations}, Count: {len(citations) if citations else 0}")
            
            response_content = data.get('content', '')
            print(f"   📝 Normal Message Response Preview: {response_content[:200]}...")
            return True
            
        else:
            self.log_test("Normal Message Uses RAG (No Web Search)", False,
                         f"Message failed: Status {status}, Data: {data}")
            return False

    def test_additional_keywords(self, chat_id: str):
        """Test additional research keywords"""
        keywords = [
            "search for information about machine learning",
            "ищи данные о нейронных сетях",
            "поищи информацию о блокчейне"
        ]
        
        for i, keyword_message in enumerate(keywords):
            success, data, status = self.make_request('POST', f'/chats/{chat_id}/messages', {
                "content": keyword_message
            }, token=self.admin_token)
            
            if success and status == 200:
                has_web_sources = 'web_sources' in data and data.get('web_sources') is not None
                web_sources = data.get('web_sources', [])
                
                self.log_test(f"Additional Keyword {i+1} Triggers Web Search", has_web_sources,
                             f"Keyword: '{keyword_message[:30]}...', web_sources: {len(web_sources) if web_sources else 0}")
            else:
                self.log_test(f"Additional Keyword {i+1} Triggers Web Search", False,
                             f"Message failed: Status {status}")

    def check_backend_logs(self):
        """Check backend logs for Brave Search mentions"""
        print("\n🔍 Checking Backend Logs for Brave Search Activity...")
        
        try:
            # Check both output and error logs
            import subprocess
            
            # Check error logs (where INFO logs are written)
            result = subprocess.run(['tail', '-n', '100', '/var/log/supervisor/backend.err.log'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                log_content = result.stdout
                
                # Look for Brave Search related logs
                brave_mentions = []
                for line in log_content.split('\n'):
                    if any(keyword in line for keyword in ['Triggering Brave Web Search', 'Brave Search returned', 'brave_web_search']):
                        brave_mentions.append(line.strip())
                
                if brave_mentions:
                    print(f"   📋 Found {len(brave_mentions)} Brave Search log entries:")
                    for mention in brave_mentions[-10:]:  # Show last 10
                        print(f"      {mention}")
                    self.log_test("Backend Logs Show Brave Search Activity", True,
                                 f"Found {len(brave_mentions)} log entries")
                else:
                    print("   📋 No Brave Search activity found in recent logs")
                    self.log_test("Backend Logs Show Brave Search Activity", False,
                                 "No Brave Search mentions in logs")
            else:
                self.log_test("Backend Logs Check", False, "Failed to read backend logs")
                
        except Exception as e:
            self.log_test("Backend Logs Check", False, f"Error checking logs: {str(e)}")

    def run_brave_search_tests(self):
        """Run all Brave Search integration tests"""
        print("🔍 Starting Brave Search Integration Tests")
        print("=" * 60)
        
        try:
            # Step 1: Login as admin
            if not self.login_admin():
                return 1
            
            # Step 2: Get or create a chat
            chat_id = self.get_or_create_chat()
            if not chat_id:
                return 1
            
            print(f"\n🗨️  Using Chat ID: {chat_id}")
            
            # Step 3: Test Russian research keyword
            print("\n📝 Testing Russian Research Keyword...")
            self.test_russian_research_keyword(chat_id)
            
            # Step 4: Test English research keyword
            print("\n📝 Testing English Research Keyword...")
            self.test_english_research_keyword(chat_id)
            
            # Step 5: Test normal message (should use RAG)
            print("\n📝 Testing Normal Message (RAG)...")
            self.test_normal_message_no_web_search(chat_id)
            
            # Step 6: Test additional keywords
            print("\n📝 Testing Additional Keywords...")
            self.test_additional_keywords(chat_id)
            
            # Step 7: Check backend logs
            self.check_backend_logs()
            
        except Exception as e:
            print(f"❌ Test suite failed with error: {str(e)}")
            return 1
        
        finally:
            # Print summary
            print("\n" + "=" * 60)
            print(f"📊 Brave Search Test Results: {self.tests_passed}/{self.tests_run} passed")
            print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            if self.tests_passed == self.tests_run:
                print("🎉 All Brave Search tests passed!")
                return 0
            else:
                print("⚠️  Some Brave Search tests failed!")
                
                # Show failed tests
                failed_tests = [t for t in self.test_results if not t['success']]
                if failed_tests:
                    print("\n❌ Failed Tests:")
                    for test in failed_tests:
                        print(f"   - {test['name']}: {test['details']}")
                
                return 1

def main():
    tester = BraveSearchTester()
    return tester.run_brave_search_tests()

if __name__ == "__main__":
    sys.exit(main())