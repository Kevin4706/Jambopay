#!/usr/bin/env python3
"""
Driveflow Enterprises - JamboPay Production Payment Server
Deployed on GitHub Codespaces
"""

import http.server
import socketserver
import json
import base64
import os
from datetime import datetime
import requests
from urllib.parse import urlparse

class JamboPayPaymentHandler(http.server.SimpleHTTPRequestHandler):
    
    def do_GET(self):
        """Serve the payment page"""
        if self.path == '/':
            self.path = '/index.html'
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        """Handle payment processing"""
        if self.path == '/process-payment':
            self.process_payment()
        else:
            self.send_error(404)
    
    def process_payment(self):
        """Process JamboPay payment with production credentials"""
        try:
            # Read and parse the request data
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payment_data = json.loads(post_data.decode('utf-8'))
            
            print(f"🔔 New payment request: {payment_data}")
            
            # Validate required fields
            required_fields = ['amount', 'currency', 'email', 'phone', 'description']
            for field in required_fields:
                if field not in payment_data or not payment_data[field]:
                    self.send_error_response(f"Missing required field: {field}")
                    return
            
            # Validate amount
            try:
                amount = float(payment_data['amount'])
                if amount < 1:
                    self.send_error_response("Minimum payment amount is 1.00")
                    return
            except ValueError:
                self.send_error_response("Invalid amount format")
                return
            
            # Process payment with JamboPay API
            result = self.process_jambopay_payment(payment_data)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
            
        except Exception as e:
            print(f"❌ Error processing payment: {str(e)}")
            self.send_error_response(f"Server error: {str(e)}")
    
    def generate_auth_header(self):
        """Generate JamboPay production authentication header"""
        client_id = "fcf01a144b63d7c1e62bffd961fec23dabeed189756ec9dd19754f9df0169336"
        client_secret = "pui4LjypD2LT9JATQvIotGnEdQqbv5uSLQ818XmWIcSkFg=="
        
        # For Basic Auth
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        return {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/json',
            'User-Agent': 'Driveflow-Enterprises/1.0'
        }
    
    def process_jambopay_payment(self, payment_data):
        """
        Process payment using JamboPay PRODUCTION API
        """
        
        # JamboPay PRODUCTION API configuration
        JAMBOPAY_CONFIG = {
            'base_url': 'https://api.jambopay.com',
            'timeout': 30
        }
        
        try:
            # Generate unique transaction reference
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            transaction_ref = f"DRIVEFLOW_{timestamp}"
            
            # Get Codespaces public URL for callbacks
            codespace_url = os.getenv('CODESPACE_URL', 'https://your-codespace-3000.app.github.dev')
            
            # Prepare JamboPay PRODUCTION API request payload
            jambopay_payload = {
                'command': 'request',
                'action': 'payment',
                'merchant': 'Driveflow Enterprises Live Cred',
                'amount': payment_data['amount'],
                'currency': payment_data['currency'],
                'description': payment_data['description'],
                'reference': transaction_ref,
                'email': payment_data['email'],
                'phone': payment_data['phone'],
                'callback_url': f'{codespace_url}/callback',
                'redirect_url': f'{codespace_url}/success',
                'metadata': {
                    'customer_email': payment_data['email'],
                    'customer_phone': payment_data['phone'],
                    'business': 'Driveflow Enterprises',
                    'source': 'github-codespaces'
                }
            }
            
            print(f"📤 Sending to JamboPay Production: {json.dumps(jambopay_payload, indent=2)}")
            
            # Make PRODUCTION API call to JamboPay
            headers = self.generate_auth_header()
            
            api_url = f"{JAMBOPAY_CONFIG['base_url']}/v1/payments"
            
            response = requests.post(
                api_url,
                json=jambopay_payload,
                headers=headers,
                timeout=JAMBOPAY_CONFIG['timeout']
            )
            
            print(f"📥 JamboPay Production Response Status: {response.status_code}")
            print(f"📥 JamboPay Production Response: {response.text}")
            
            if response.status_code in [200, 201]:
                api_response = response.json()
                
                # Handle JamboPay API response
                if api_response.get('success') or api_response.get('status') == 'success':
                    return {
                        'success': True,
                        'transactionId': transaction_ref,
                        'paymentUrl': api_response.get('payment_url') or api_response.get('checkout_url'),
                        'message': 'Payment initiated successfully',
                        'amount': payment_data['amount'],
                        'currency': payment_data['currency'],
                        'status': api_response.get('status', 'initiated'),
                        'timestamp': datetime.now().isoformat(),
                        'apiResponse': api_response
                    }
                else:
                    error_msg = api_response.get('message') or api_response.get('error') or 'Payment initiation failed'
                    return {
                        'success': False,
                        'error': f'JamboPay API Error: {error_msg}',
                        'apiResponse': api_response
                    }
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail.get('message', response.text)}"
                except:
                    error_msg += f" - {response.text}"
                
                return {
                    'success': False,
                    'error': f'API request failed: {error_msg}'
                }
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'JamboPay API timeout - please try again'
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Network connection error - please check your connection'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }
        except Exception as e:
            print(f"❌ JamboPay processing error: {str(e)}")
            return {
                'success': False,
                'error': f'Payment processing failed: {str(e)}'
            }
    
    def send_error_response(self, message):
        """Send error response"""
        self.send_response(400)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        error_response = {
            'success': False,
            'error': message
        }
        self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Custom log message format"""
        print(f"🌐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {format % args}")

def run_server():
    """Run the production payment server"""
    PORT = 8000
    
    # Create the server
    with socketserver.TCPServer(("", PORT), JamboPayPaymentHandler) as httpd:
        print("🚀 Driveflow Enterprises - JamboPay Production Server")
        print("=" * 50)
        print(f"📍 Local URL: http://localhost:{PORT}")
        print(f"🌍 Public URL: https://{os.getenv('CODESPACE_NAME', 'your-codespace')}-{PORT}.app.github.dev")
        print("🔐 Using PRODUCTION JamboPay credentials")
        print("🏢 Merchant: Driveflow Enterprises Live Cred")
        print("⏰ Server started at:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print("=" * 50)
        print("⏹️  Press Ctrl+C to stop the server")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped gracefully")

if __name__ == "__main__":
    run_server()
