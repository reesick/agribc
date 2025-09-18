import os
import json
import tempfile
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime

import google.generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from supabase import create_client, Client

from models import *

class SupabaseService:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_KEY")
        self.client: Client = create_client(self.url, self.key)
    
    # User operations
    def create_user_profile(self, user_id: str, name: str, role: str) -> Dict:
        """Create user profile and wallet after Supabase auth signup"""
        # Create user
        result = self.client.table("users").insert({
            "id": user_id,
            "name": name,
            "role": role
        }).execute()
        
        # Auto-create wallet with 0 balance
        self.client.table("wallets").insert({
            "user_id": user_id,
            "balance": 0.00
        }).execute()
        
        return result.data[0] if result.data else None
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        result = self.client.table("users").select("*").eq("id", user_id).execute()
        return result.data[0] if result.data else None
    
    # Wallet operations
    def get_wallet(self, user_id: str) -> Optional[Dict]:
        result = self.client.table("wallets").select("*").eq("user_id", user_id).execute()
        return result.data[0] if result.data else None
    
    def add_funds(self, user_id: str, amount: Decimal) -> Dict:
        wallet = self.get_wallet(user_id)
        if not wallet:
            # Create wallet if it doesn't exist
            self.client.table("wallets").insert({
                "user_id": user_id,
                "balance": float(amount)
            }).execute()
            return self.get_wallet(user_id)
        
        new_balance = Decimal(str(wallet["balance"])) + amount
        
        result = self.client.table("wallets").update({
            "balance": float(new_balance)
        }).eq("user_id", user_id).execute()
        return result.data[0]
    
    def transfer_funds(self, from_user_id: str, to_user_id: str, amount: Decimal) -> bool:
        """Transfer funds from one user to another"""
        try:
            # Debit from sender
            from_wallet = self.get_wallet(from_user_id)
            from_balance = Decimal(str(from_wallet["balance"])) - amount
            
            if from_balance < 0:
                return False
            
            self.client.table("wallets").update({
                "balance": float(from_balance)
            }).eq("user_id", from_user_id).execute()
            
            # Credit to receiver
            to_wallet = self.get_wallet(to_user_id)
            to_balance = Decimal(str(to_wallet["balance"])) + amount
            
            self.client.table("wallets").update({
                "balance": float(to_balance)
            }).eq("user_id", to_user_id).execute()
            
            return True
        except Exception as e:
            print(f"Transfer failed: {e}")
            return False
    
    # Listing operations
    def create_listing(self, farmer_id: str, listing_data: ListingCreate) -> Dict:
        result = self.client.table("listings").insert({
            "farmer_id": farmer_id,
            "crop_type": listing_data.crop_type,
            "quantity": listing_data.quantity,
            "delivery_date": listing_data.delivery_date.isoformat(),
            "expected_price": float(listing_data.expected_price)
        }).execute()
        return result.data[0]
    
    def get_all_listings(self) -> List[Dict]:
        result = self.client.table("listings").select("*").eq("status", "open").execute()
        return result.data
    
    def get_farmer_listings(self, farmer_id: str) -> List[Dict]:
        result = self.client.table("listings").select("*").eq("farmer_id", farmer_id).execute()
        return result.data
    
    # Proposal operations
    def create_proposal(self, buyer_id: str, proposal_data: ProposalCreate) -> Dict:
        result = self.client.table("proposals").insert({
            "listing_id": proposal_data.listing_id,
            "buyer_id": buyer_id,
            "price": float(proposal_data.price),
            "payment_terms": proposal_data.payment_terms
        }).execute()
        return result.data[0]
    
    def get_proposals_for_listing(self, listing_id: str) -> List[Dict]:
        result = self.client.table("proposals").select("*").eq("listing_id", listing_id).execute()
        return result.data
    
    def get_buyer_proposals(self, buyer_id: str) -> List[Dict]:
        result = self.client.table("proposals").select("*").eq("buyer_id", buyer_id).execute()
        return result.data
    
    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        result = self.client.table("proposals").select("*").eq("id", proposal_id).execute()
        return result.data[0] if result.data else None
    
    def update_proposal_status(self, proposal_id: str, status: str) -> Dict:
        result = self.client.table("proposals").update({"status": status}).eq("id", proposal_id).execute()
        return result.data[0]
    
    # Contract operations
    def create_contract(self, listing_id: str, farmer_id: str, buyer_id: str, 
                       contract_text: str, pdf_url: str) -> Dict:
        result = self.client.table("contracts").insert({
            "listing_id": listing_id,
            "farmer_id": farmer_id,
            "buyer_id": buyer_id,
            "contract_text": contract_text,
            "pdf_url": pdf_url
        }).execute()
        return result.data[0]
    
    def get_contract(self, contract_id: str) -> Optional[Dict]:
        result = self.client.table("contracts").select("*").eq("id", contract_id).execute()
        return result.data[0] if result.data else None
    
    def get_user_contracts(self, user_id: str) -> List[Dict]:
        # Replace .or_() with two separate queries
        farmer_contracts = self.client.table("contracts").select("*").eq("farmer_id", user_id).execute()
        buyer_contracts = self.client.table("contracts").select("*").eq("buyer_id", user_id).execute()
        
        # Combine results and remove duplicates
        all_contracts = farmer_contracts.data + buyer_contracts.data
        seen_ids = set()
        unique_contracts = []
        for contract in all_contracts:
            if contract["id"] not in seen_ids:
                unique_contracts.append(contract)
                seen_ids.add(contract["id"])
        
        return unique_contracts
    
    def sign_contract(self, contract_id: str, user_id: str) -> Dict:
        contract = self.get_contract(contract_id)
        signed_by = json.loads(contract["signed_by"]) if contract["signed_by"] else []
        
        if user_id not in signed_by:
            signed_by.append(user_id)
        
        # Check if both parties have signed
        status = "signed" if len(signed_by) == 2 else "drafted"
        
        result = self.client.table("contracts").update({
            "signed_by": json.dumps(signed_by),
            "status": status
        }).eq("id", contract_id).execute()
        
        return result.data[0]
    
    def upload_file(self, file_path: str, bucket_name: str = "contracts") -> str:
        """Upload file to Supabase storage and return public URL"""
        try:
            with open(file_path, 'rb') as file:
                file_name = f"contract_{datetime.now().timestamp()}.pdf"
                result = self.client.storage.from_(bucket_name).upload(file_name, file)
                
            # Get public URL
            public_url = self.client.storage.from_(bucket_name).get_public_url(file_name)
            return public_url
        except Exception as e:
            print(f"Storage upload failed: {e}")
            # Return a placeholder URL if storage fails
            return f"https://placeholder.com/contract_{datetime.now().timestamp()}.pdf"


class GeminiService:
    def __init__(self):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        # Changed from 'gemini-pro' to 'gemini-1.5-flash' for free tier
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def generate_contract(self, farmer_data: Dict, buyer_data: Dict, 
                         listing_data: Dict, proposal_data: Dict) -> str:
        """Generate contract text using Gemini Flash 1.5 AI"""
        
        prompt = f"""
        Generate a simple crop purchase contract with the following details:
        
        FARMER (SELLER):
        - Name: {farmer_data['name']}
        - Role: Farmer/Seller
        
        BUYER:
        - Name: {buyer_data['name']}
        - Role: Buyer
        
        CROP DETAILS:
        - Crop Type: {listing_data['crop_type']}
        - Quantity: {listing_data['quantity']} units
        - Delivery Date: {listing_data['delivery_date']}
        - Agreed Price: ₹{proposal_data['price']}
        - Payment Terms: {proposal_data.get('payment_terms', 'Payment on delivery')}
        
        Please generate a clear, legally-formatted contract in English that includes:
        1. Contract title and date
        2. Party details
        3. Crop specifications
        4. Price and payment terms
        5. Delivery terms
        6. Basic terms and conditions
        7. Signature lines
        
        Keep it professional but simple to understand for farmers and buyers.
        Format it properly with clear sections and make it look professional.
        """
        
        try:
            # Using generate_content for Gemini Flash 1.5
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Gemini Flash API error: {e}")
            # Fall back to template contract
            return self._fallback_contract(farmer_data, buyer_data, listing_data, proposal_data)
    
    def _fallback_contract(self, farmer_data: Dict, buyer_data: Dict, 
                          listing_data: Dict, proposal_data: Dict) -> str:
        """Fallback contract template if Gemini fails"""
        return f"""
        CROP PURCHASE CONTRACT
        
        Contract Date: {datetime.now().strftime('%Y-%m-%d')}
        Contract ID: CRP-{datetime.now().strftime('%Y%m%d%H%M%S')}
        
        PARTIES TO THE CONTRACT:
        
        SELLER (FARMER):
        Name: {farmer_data['name']}
        Role: Agricultural Producer/Seller
        
        BUYER:
        Name: {buyer_data['name']}
        Role: Purchaser
        
        CROP PURCHASE DETAILS:
        
        1. CROP SPECIFICATION:
           - Crop Type: {listing_data['crop_type']}
           - Quantity: {listing_data['quantity']} units
           - Quality: As per standard market grade
        
        2. DELIVERY TERMS:
           - Delivery Date: {listing_data['delivery_date']}
           - Delivery Location: To be mutually agreed
        
        3. PRICING & PAYMENT:
           - Total Contract Value: ₹{proposal_data['price']}
           - Payment Terms: {proposal_data.get('payment_terms', 'Payment on successful delivery')}
        
        4. TERMS & CONDITIONS:
           - The seller agrees to deliver the specified quantity of crop
           - The buyer agrees to accept delivery and make payment as agreed
           - Both parties agree to the terms mentioned above
        
        SIGNATURES:
        
        Seller (Farmer): ________________    Date: ___________
        {farmer_data['name']}
        
        Buyer: ________________             Date: ___________
        {buyer_data['name']}
        
        This contract is binding upon both parties.
        """


class PDFService:
    def create_contract_pdf(self, contract_text: str) -> str:
        """Create PDF from contract text and return file path"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            doc = SimpleDocTemplate(tmp_file.name, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Add contract text as paragraphs
            for line in contract_text.split('\n'):
                if line.strip():
                    story.append(Paragraph(line, styles['Normal']))
                    story.append(Spacer(1, 12))
            
            doc.build(story)
            return tmp_file.name


class WalletService:
    def __init__(self, supabase_service: SupabaseService):
        self.supabase = supabase_service
    
    def process_contract_payment(self, contract_id: str) -> bool:
        """Process payment when contract is fully signed"""
        contract = self.supabase.get_contract(contract_id)
        if not contract or contract['status'] != 'signed':
            return False
        
        # Get proposal to get the price
        proposal = self.supabase.client.table("proposals").select("*").eq("listing_id", contract['listing_id']).execute()
        if not proposal.data:
            return False
        
        price = Decimal(str(proposal.data[0]['price']))
        
        # Transfer funds from buyer to farmer
        success = self.supabase.transfer_funds(
            contract['buyer_id'], 
            contract['farmer_id'], 
            price
        )
        
        if success:
            # Update contract status
            self.supabase.client.table("contracts").update({
                "status": "completed"
            }).eq("id", contract_id).execute()
        
        return success