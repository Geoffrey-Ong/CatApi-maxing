from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Simple Cat API",
    description="A beginner-friendly REST API containing information about cats.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CAT DATA
cats = [
    {
        "id": 1,
        "name": "Whiskers",
        "breed": "Maine Coon",
        "age": 3,
        "color": "Brown and White",
        "description": "A large, friendly cat with a thick coat and full of sodium."
    },

    {
        "id": 2,
        "name": "Luna",
        "breed": "Siamese",
        "age": 2,
        "color": "Cream and Brown",
        "description": "A vocal and affectionate cat.(Will get political)"
    },

    {
        "id": 3,
        "name": "Simba",
        "breed": "Russian Blue",
        "age": 5,
        "color": "Golden",
        "description": "A majestic cat with a powerful presence and has a raging anger with slippers."
    },

    {
        "id": 4,
        "name": "Bacteria",
        "breed": "Ragdoll",
        "age": "1",
        "color": "Brown and White",
        "description": "A gentle and affectionate cat, will stab you in your sleep."
    },

    {
        "id": 5,
        "name": "Chromosome",
        "breed": "Burmese",
        "age": "1",
        "color": "Brown, Black and White",
        "description": "A playful and curious cat, will eat your food when you are not looking, including dino nuggies."
    },

]
        
# HOME
@app.get("/")
def home():

    return {
        "message": "Welcome to the Simple Cat API!",
        "endpoints": [
            "/cats",
            "/cats/{id}",
            "/cats/search"
        ]
    }


# GET ALL CATS
@app.get("/cats")
def get_cats():

    return {
        "count": len(cats),
        "cats": cats
    }

# SEARCH CATS
@app.get("/cats/search")
def search_cats( q: str = Query(..., min_length=1)):
    q = q.lower()
    results = []
    for cat in cats:
        searchable_text = (
            f"{cat['name']} "
            f"{cat['breed']} "
            f"{cat['color']}"
        ).lower()

        if q in searchable_text:
            results.append(cat)

    return {
        "query": q,
        "count": len(results),
        "results": results
    }


# GET ONE CAT
@app.get("/cats/{cat_id}")
def get_cat(cat_id: int):

    for cat in cats:

        if cat["id"] == cat_id:
            return cat

    raise HTTPException(
        status_code=404,
        detail="Cat not found."
    )


