import os
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models import (
    APIResponse,
    UserCreate,
    WalletAddFunds,
    Wallet,
    Listing,
    ListingCreate,
    Proposal,
    ProposalCreate,
    Contract,
    ContractGenerate
)
from services import SupabaseService, GeminiService, PDFService, WalletService

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Crop Contract API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
supabase_service = SupabaseService()
gemini_service = GeminiService()
pdf_service = PDFService()
wallet_service = WalletService(supabase_service)


# ----------------------------------------------------------------
# Base Routes
# ----------------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "Crop Contract API is running!"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}


# ----------------------------------------------------------------
# User Routes
# ----------------------------------------------------------------
@app.post("/users", response_model=APIResponse)
async def create_user_profile(user_data: UserCreate, user_id: str):
    """Create user profile after Supabase auth signup"""
    try:
        user = supabase_service.create_user_profile(user_id, user_data.name, user_data.role)
        return APIResponse(success=True, message="User profile created", data=user)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------------------------------------------
# Wallet Routes
# ----------------------------------------------------------------
from pydantic import BaseModel

class WalletAddFundsRequest(WalletAddFunds):
    user_id: str  # include user_id in the body

@app.post("/wallet/add-funds", response_model=APIResponse)
async def add_funds_to_wallet(request: WalletAddFundsRequest):
    """Add funds to user's wallet"""
    try:
        wallet = supabase_service.add_funds(request.user_id, request.amount)
        return APIResponse(success=True, message="Funds added successfully", data=wallet)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




@app.get("/wallet/{user_id}", response_model=Wallet)
async def get_wallet_balance(user_id: str):
    """Get user's wallet balance"""
    try:
        wallet = supabase_service.get_wallet(user_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        return wallet
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------------------------------------------
# Dashboard Routes
# ----------------------------------------------------------------
@app.get("/dashboard/farmer/{farmer_id}", response_model=APIResponse)
async def get_farmer_dashboard(farmer_id: str):
    """Get farmer's dashboard data"""
    try:
        # Get user info
        user = supabase_service.get_user(farmer_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get wallet
        wallet = supabase_service.get_wallet(farmer_id)

        # Get farmer's listings
        listings = supabase_service.get_farmer_listings(farmer_id)

        # Get proposals for farmer's listings
        all_proposals = []
        for listing in listings:
            proposals = supabase_service.get_proposals_for_listing(listing["id"])
            all_proposals.extend(proposals)

        # Get contracts
        contracts = supabase_service.get_user_contracts(farmer_id)

        dashboard_data = {
            "user": user,
            "wallet": wallet,
            "listings": listings,
            "proposals": all_proposals,
            "contracts": contracts
        }

        return APIResponse(success=True, message="Dashboard data retrieved", data=dashboard_data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/dashboard/buyer/{buyer_id}", response_model=APIResponse)
async def get_buyer_dashboard(buyer_id: str):
    """Get buyer's dashboard data"""
    try:
        # Get user info
        user = supabase_service.get_user(buyer_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get wallet
        wallet = supabase_service.get_wallet(buyer_id)

        # Get all available listings
        all_listings = supabase_service.get_all_listings()

        # Get buyer's proposals
        my_proposals = supabase_service.get_buyer_proposals(buyer_id)

        # Get contracts
        contracts = supabase_service.get_user_contracts(buyer_id)

        dashboard_data = {
            "user": user,
            "wallet": wallet,
            "all_listings": all_listings,
            "my_proposals": my_proposals,
            "contracts": contracts
        }

        return APIResponse(success=True, message="Dashboard data retrieved", data=dashboard_data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------------------------------------------
# Listing Routes
# ----------------------------------------------------------------
@app.post("/listings", response_model=APIResponse)
async def create_listing(listing_data: ListingCreate, farmer_id: str):
    """Farmer creates a new crop listing"""
    try:
        listing = supabase_service.create_listing(farmer_id, listing_data)
        return APIResponse(success=True, message="Listing created", data=listing)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/listings", response_model=List[Listing])
async def get_all_listings():
    """Get all available crop listings"""
    try:
        listings = supabase_service.get_all_listings()
        return listings
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------------------------------------------
# Proposal Routes
# ----------------------------------------------------------------
@app.post("/proposals", response_model=APIResponse)
async def create_proposal(proposal_data: ProposalCreate, buyer_id: str):
    """Buyer creates a proposal for a listing"""
    try:
        proposal = supabase_service.create_proposal(buyer_id, proposal_data)
        return APIResponse(success=True, message="Proposal created", data=proposal)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/proposals/{proposal_id}/accept", response_model=APIResponse)
async def accept_proposal(proposal_id: str):
    """Farmer accepts a proposal"""
    try:
        proposal = supabase_service.update_proposal_status(proposal_id, "accepted")
        return APIResponse(success=True, message="Proposal accepted", data=proposal)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/proposals/listing/{listing_id}", response_model=List[Proposal])
async def get_proposals_for_listing(listing_id: str):
    """Get all proposals for a specific listing"""
    try:
        proposals = supabase_service.get_proposals_for_listing(listing_id)
        return proposals
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------------------------------------------
# Contract Routes
# ----------------------------------------------------------------
@app.get("/contracts/{contract_id}", response_model=Contract)
async def get_contract(contract_id: str):
    """Get contract details"""
    try:
        contract = supabase_service.get_contract(contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        return contract
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/contracts/generate", response_model=APIResponse)
async def generate_contract(contract_data: ContractGenerate):
    """Generate contract from accepted proposal"""
    try:
        # Get proposal details
        proposal = supabase_service.get_proposal(contract_data.proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        # Get listing details
        listing = supabase_service.client.table("listings").select("*").eq("id", proposal["listing_id"]).execute()
        if not listing.data:
            raise HTTPException(status_code=404, detail="Listing not found")
        listing = listing.data[0]

        # Get user details
        farmer = supabase_service.get_user(listing["farmer_id"])
        buyer = supabase_service.get_user(proposal["buyer_id"])

        # Generate contract text with Gemini
        contract_text = gemini_service.generate_contract(farmer, buyer, listing, proposal)

        # Create PDF
        pdf_path = pdf_service.create_contract_pdf(contract_text)

        # Upload PDF to Supabase storage
        pdf_url = supabase_service.upload_file(pdf_path)

        # Create contract record
        contract = supabase_service.create_contract(
            listing["id"],
            listing["farmer_id"],
            proposal["buyer_id"],
            contract_text,
            pdf_url
        )

        # Clean up temp file
        os.unlink(pdf_path)

        return APIResponse(success=True, message="Contract generated", data=contract)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/contracts/{contract_id}/sign", response_model=APIResponse)
async def sign_contract(contract_id: str, user_id: str):
    """User signs a contract (fake DigiLocker)"""
    try:
        # Update contract with user's signature
        contract = supabase_service.sign_contract(contract_id, user_id)

        # If both parties signed, process payment
        if contract["status"] == "signed":
            payment_success = wallet_service.process_contract_payment(contract_id)
            message = "Contract signed and payment processed" if payment_success else "Contract signed but payment failed"
        else:
            message = "Contract signed, waiting for other party"

        return APIResponse(success=True, message=message, data=contract)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------------------------------------------
# Run App
# ----------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
