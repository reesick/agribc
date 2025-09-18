from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

# User Models
class UserCreate(BaseModel):
    name: str
    role: str = Field(..., pattern="^(farmer|buyer)$")  # Changed from regex to pattern

class User(BaseModel):
    id: str
    name: str
    role: str
    created_at: datetime

# Listing Models
class ListingCreate(BaseModel):
    crop_type: str
    quantity: int = Field(..., gt=0)
    delivery_date: date
    expected_price: Decimal = Field(..., gt=0)

class Listing(BaseModel):
    id: str
    farmer_id: str
    crop_type: str
    quantity: int
    delivery_date: date
    expected_price: Decimal
    status: str
    created_at: datetime

# Proposal Models
class ProposalCreate(BaseModel):
    listing_id: str
    price: Decimal = Field(..., gt=0)
    payment_terms: Optional[str] = None

class Proposal(BaseModel):
    id: str
    listing_id: str
    buyer_id: str
    price: Decimal
    payment_terms: Optional[str]
    status: str
    created_at: datetime

# Contract Models
class ContractGenerate(BaseModel):
    proposal_id: str

class Contract(BaseModel):
    id: str
    listing_id: str
    farmer_id: str
    buyer_id: str
    contract_text: Optional[str]
    pdf_url: Optional[str]
    status: str
    signed_by: List[str]
    created_at: datetime

class SignContract(BaseModel):
    contract_id: str

# Wallet Models
class WalletAddFunds(BaseModel):
    amount: Decimal = Field(..., gt=0)

class Wallet(BaseModel):
    id: str
    user_id: str
    balance: Decimal
    created_at: datetime

# Dashboard Models
class FarmerDashboard(BaseModel):
    user: User
    wallet: Wallet
    listings: List[Listing]
    proposals: List[Proposal]
    contracts: List[Contract]

class BuyerDashboard(BaseModel):
    user: User
    wallet: Wallet
    all_listings: List[Listing]
    my_proposals: List[Proposal]
    contracts: List[Contract]

# Response Models
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None