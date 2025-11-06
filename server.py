#!/usr/bin/env python3
"""
Driveflow Enterprises - JamboPay Production Payment Server
With Enhanced Error Handling
"""

import http.server
import socketserver
import json
import base64
import os
from datetime import datetime
import requests
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
        """Process JamboPay payment with enhanced error handling"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payment_data = json.loads(post_data.decode('utf-8'))
            
            logging.info(f"New payment request: {payment_data}")
            
            # Validate required fields
            required_fields = ['amount', 'currency', 'email', 'phone', 'description']
            for field in required_fields:
                if field not in payment_data or not payment_data[field]:
                    self.send_error_response(f"Missing required field: {field}")
                    return
            
            # Process payment
            result = self.process_jambopay_payment(payment_data)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
            
        except Exception as e:
            logging.error(f"Error processing payment: {str(e)}")
            self.send_error_response(f"Server error: {str(e)}")
    
    def generate_auth_header(self):
        """Generate JamboPay authentication header"""
        client_id = "fcf01a144b63d7c1e62bffd961fec23dabeed189756ec9dd19754f9df0169336"
        client_secret = "pui4LjypD2LT9JATQvIotGnEdQqbv5uSLQ818XmWIcSkFg=="
        
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        return {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def process_jambopay_payment(self, payment_data):
        """
        Process payment using JamboPay PRODUCTION API with better debugging
        """
        
        JAMBOPAY_CONFIG = {
            'base_url': 'https://api.jambopay.com',
            'timeout': 30
        }
        
        try:
            # Generate transaction reference
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            transaction_ref = f"DRIVEFLOW_{timestamp}"
            
            # Get current URL for callbacks
            current_url = os.getenv('CODESPACE_URL', 'https://al-halibut-gv5qxg67g7v299xp-8000.app.github.dev')
            
            # Enhanced payload - try different JamboPay formats
            jambopay_payload = {
                # Format 1: Standard payment request
                'merchant': 'Driveflow Enterprises Live Cred',
                'amount': payment_data['amount'],
                'currency': payment_data['currency'],
                'description': payment_data['description'],
                'reference': transaction_ref,
                'email': payment_data['email'],
                'phone': payment_data['phone'],
                'callback_url': f'{current_url}/callback',
                'redirect_url': f'{current_url}/success',
                
                # Additional fields that might be required
                'first_name': 'Customer',
                'last_name': 'User',
                'country': 'KE'
            }
            
            logging.info(f"Sending payload to JamboPay: {json.dumps(jambopay_payload, indent=2)}")
            
            headers = self.generate_auth_header()
            
            # Try different JamboPay endpoints
            endpoints = [
                f"{JAMBOPAY_CONFIG['base_url']}/v1/payments",
                f"{JAMBOPAY_CONFIG['base_url']}/api/v1/payments",
                f"{JAMBOPAY_CONFIG['base_url']}/checkout/create"
            ]
            
            response = None
            last_error = None
            
            for endpoint in endpoints:
                try:
                    logging.info(f"Trying endpoint: {endpoint}")
                    
                    response = requests.post(
                        endpoint,
                        json=jambopay_payload,
                        headers=headers,
                        timeout=JAMBOPAY_CONFIG['timeout'],
                        verify=True
                    )
                    
                    logging.info(f"Response status: {response.status_code}")
                    logging.info(f"Response headers: {dict(response.headers)}")
                    logging.info(f"Response body: {response.text}")
                    
                    if response.status_code in [200, 201]:
                        break
                        
                except requests.exceptions.RequestException as e:
                    last_error = e
                    logging.warning(f"Endpoint {endpoint} failed: {str(e)}")
                    continue
            
            if response is None:
                return {
                    'success': False,
                    'error': f'All API endpoints failed. Last error: {str(last_error)}'
                }
            
            # Parse response
            try:
                api_response = response.json()
            except:
                api_response = {'raw_response': response.text}
            
            if response.status_code in [200, 201]:
                if api_response.get('success') or api_response.get('status') == 'success':
                    return {
                        'success': True,
                        'transactionId': transaction_ref,
                        'paymentUrl': api_response.get('payment_url') or api_response.get('checkout_url') or api_response.get('url'),
                        'message': 'Payment initiated successfully',
                        'amount': payment_data['amount'],
                        'currency': payment_data['currency'],
                        'status': api_response.get('status', 'initiated'),
                        'timestamp': datetime.now().isoformat(),
                        'debug': {
                            'endpoint_used': endpoint,
                            'response_code': response.status_code
                        }
                    }
                else:
                    error_msg = api_response.get('message') or api_response.get('error') or 'Payment initiation failed'
                    return {
                        'success': False,
                        'error': f'JamboPay API Error: {error_msg}',
                        'debug': {
                            'response': api_response,
                            'status_code': response.status_code,
                            'endpoint': endpoint
                        }
                    }
            else:
                error_msg = f"HTTP {response.status_code}"
                if isinstance(api_response, dict):
                    error_msg += f" - {api_response.get('message', response.text)}"
                else:
                    error_msg += f" - {response.text}"
                
                return {
                    'success': False,
                    'error': f'API request failed: {error_msg}',
                    'debug': {
                        'status_code': response.status_code,
                        'response': api_response,
                        'endpoint': endpoint
                    }
                }
            
        except Exception as e:
            logging.error(f"JamboPay processing error: {str(e)}")
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
        logging.info(format % args)

def run_server():
    """Run the production payment server"""
    PORT = 8000
    
    with socketserver.TCPServer(("", PORT), JamboPayPaymentHandler) as httpd:
        print("🚀 Driveflow Enterprises - JamboPay Production Server")
        print("==================================================")
        print(f"📍 Local URL: http://localhost:{PORT}")
        print(f"🌍 Public URL: https://{os.getenv('CODESPACE_NAME', 'al-halibut-gv5qxg67g7v299xp')}-8000.app.github.dev")
        print("🔐 Using PRODUCTION JamboPay credentials")
        print("🏢 Merchant: Driveflow Enterprises Live Cred")
        print("🐛 DEBUG MODE: Enhanced logging enabled")
        print("==================================================")
        print("⏹️  Press Ctrl+C to stop the server")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped gracefully")

if __name__ == "__main__":
    run_server()
