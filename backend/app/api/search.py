from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas.search import SearchQuery, SearchResponse
from app.services.search import search

router = APIRouter()


@router.get("/api/v1/search", response_model=SearchResponse)
def search_endpoint(request: Request, session: Session = Depends(get_db)):
    query = SearchQuery.from_params(request.query_params.multi_items())
    return search(session, query)
