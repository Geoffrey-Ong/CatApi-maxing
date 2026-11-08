from fastapi import FastAPI, HTTPException, Header, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Literal 

# Each frontend gets its own key. The value is that key's "scope" — which
# routes it's allowed to call (see require_scope below). Both frontends
# currently read the same cat data, so both scopes are accepted on the
# existing routes; a future battle-only route (submitting a move, starting
# a match, etc.) can be locked to just "battle" by passing require_scope("battle").
API_KEYS = {
    "adoption-api-key-9770": "adoption",                # Cat Adoption 
    "catTCGcollection-api-key-6767": "collection",      # Cat TCG Home / Collection frontend
    "catTCGbattle-api-key-4242": "battle",              # Cat TCG Battle Owners frontend
    "carchive-api-key-5150": "archive",                 # CArchive of our own (the only scope allowed to submit cats)
}
API_VERSION = "1.0"


app = FastAPI(
    title="Simple Cat API",
    description="A beginner-friendly REST API containing information about cats.",
    version= API_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

#DATA MODEL
class Cat(BaseModel):
    id: int
    name: str = Field(min_length=1)
    image: str = Field(min_length=1)
    breed: str = Field(min_length=1)
    age: int = Field(gt=0)
    color: str = Field(min_length=1)
    gender: str = Field(min_length=1)
    prev_owner: str = Field(min_length=1)
    fav_treat: str = Field(min_length=1)
    likes: str 
    dislikes: str 
    previous_health_conditions: str = Field(min_length=1)
    friendliness_level: int = Field(ge=1, le=5)
    prefered_environment: str = Literal["Inside Only", "Outside Only", "Outside and Inside"]
    good_for_adoption: str = Field(min_length=1)
    description: str = Field(min_length=1)

# CAT DATA
cats = [
    {
        "id": 1,
        "name": "Whiskers",
        "image": "images/whiskers.jpg",
        "breed": "Maine Coon",
        "age": 3,
        "color": "Brown and White",
        "gender": "Male",
        "prev_owner": "Terry Cruz",
        "fav_treat": "Cat-Man-Doo Extra Large Dried Bonito Flakes",
        "likes": "Long walks at the beach",
        "dislikes": "Loud noises",
        "previous_health_conditions": "None",
        "friendliness_level": 5,
        "prefered_environment": "Outside and Inside",
        "good_for_adoption": "Yes",
        "description": "A large, friendly cat with a thick coat and full of sodium."
    },
 
    {
        "id": 2,
        "name": "Luna",
        "image": "images/luna.jpg",
        "breed": "Siamese",
        "age": 2,
        "color": "Cream and Brown",
        "gender": "Female",
        "prev_owner": "Lexter Launion",
        "fav_treat": "Anything that tastes like fish",
        "likes": "Playing with yarn balls",
        "dislikes": "Abadonment",
        "previous_health_conditions": "None",
        "friendliness_level": 4,
        "prefered_environment": "Inside Only",
        "good_for_adoption": "Yes",
        "description": "A vocal and affectionate cat.(Will get political)"
    },
 
    {
        "id": 3,
        "name": "Simba",
        "image": "images/simba.jpg",
        "breed": "Russian Blue",
        "age": 3,
        "color": "Golden",
        "gender": "Male",
        "prev_owner": "Orie Mano",
        "fav_treat": "The souls of the damned",
        "likes": "Alone time",
        "dislikes": "Slippers",
        "previous_health_conditions": "Fleas",
        "friendliness_level": 2,
        "prefered_environment": "Inside Only",
        "good_for_adoption": "Yes",
        "description": "A majestic cat with a powerful presence and has a raging anger with slippers."
    },
 
    {
        "id": 4,
        "name": "Bacteria",
        "image": "images/bacteria.jpg",
        "breed": "Ragdoll",
        "age": 1,
        "color": "Brown and White",
        "gender": "Male",
        "prev_owner": "Wambi Erie",
        "fav_treat": "Tuna",
        "likes": "Sleeping",
        "dislikes": "Markiplier",
        "previous_health_conditions": "Diabetes",
        "friendliness_level": 5,
        "prefered_environment": "Inside Only",
        "good_for_adoption": "Yes",
        "description": "A gentle and affectionate cat, will stab you in your sleep."
    },
 
    {
        "id": 5,
        "name": "Chromosome",
        "image": "images/chromosome.jpg",
        "breed": "Burmese",
        "age": 1,
        "color": "Brown, Black and White",
        "gender": "Male",
        "prev_owner": "Anonymous",
        "fav_treat": "Chicken Nuggets",
        "likes": "Eating",
        "dislikes": "Not being given treats",
        "previous_health_conditions": "Obesity",
        "friendliness_level": 5,
        "prefered_environment": "Inside Only",
        "good_for_adoption": "No",
        "description": "A playful and curious cat, will eat your food when you are not looking, including dino nuggies."
    },
 
    {
        "id": 6,
        "name": "Biggie Cheese",
        "image": "images/biggie-cheese.jpg",
        "breed": "American Longhair",
        "age": 1,
        "color": "Brown, Black and White",
        "gender": "Female",
        "prev_owner": "Ryan Salmo",
        "fav_treat": "Tuna fish",
        "likes": "Sleeping 17 hours",
        "dislikes": "Disruption of said sleep",
        "previous_health_conditions": "None",
        "friendliness_level": 3,
        "prefered_environment": "Inside Only",
        "good_for_adoption": "Yes",
        "description": "A rather sleepy cat that mostly sleeps in his freetime or whatever time really. Will slap you if you disrupt his beauty sleep"
    },
 
    {
        "id": 7,
        "name": "Burmese Python",
        "image": "images/burmese-python.jpg",
        "breed": "Donskoy",
        "age": 2,
        "color": "Grey",
        "gender": "Female",
        "prev_owner": "Anonymous", 
        "fav_treat": "Water",
        "likes": "Bathing in the Sun",
        "dislikes": "Showers",
        "previous_health_conditions": "None",
        "friendliness_level": 5, 
        "prefered_environment": "Outside and Inside",
        "good_for_adoption": "Yes",
        "description": "This cat likes to be praised alot. I don't know why but just praise her and she'll love you. (Alot)"
    },
 
    {
        "id": 8,
        "name": "King",
        "image": "images/king.jpg",
        "breed": "Persian",
        "age": 1,
        "color": "White",
        "gender": "Male",
        "prev_owner": "Leon Kennedy", 
        "fav_treat": "Will eat anything",
        "likes": "Sitting on a big chair",
        "dislikes": "Being yelled at",
        "previous_health_conditions": "None",
        "friendliness_level": 2, 
        "prefered_environment": "Outside and Inside",
        "good_for_adoption": "Yes",
        "description": "He likes staring down at people at a high place for some reason."
    },
 
    {
        "id": 9,
        "name": "Larry",
        "image": "images/larry.jpg",
        "breed": "Persian",
        "age": 3,
        "color": "Grey",
        "gender": "Male",
        "prev_owner": "Anonymous", 
        "fav_treat": "Cheese",
        "likes": "Cheese",
        "dislikes": "Anything but cheese",
        "previous_health_conditions": "None",
        "friendliness_level": 5, 
        "prefered_environment": "Inside Only",
        "good_for_adoption": "Yes",
        "description": "Larry."
    },
 
    {
        "id": 10,
        "name": "Evil Larry",
        "image": "images/evil-larry.jpg",
        "breed": "Scottish Fold",
        "age": 1,
        "color": "Orange",
        "gender": "Female",
        "prev_owner": "Anonymous", 
        "fav_treat": "Eggs",
        "likes": "Everything but Larry",
        "dislikes": "Larry",
        "previous_health_conditions": "None",
        "friendliness_level": 1, 
        "prefered_environment": "Inside Only",
        "good_for_adoption": "No",
        "description": "Do not let her near Larry, at all cost."
    },
 
    {
        "id": 11,
        "name": "Irish",
        "image": "images/irish.jpg",
        "breed": "Siamese",
        "age": 1,
        "color": "Orange and white",
        "gender": "Female",
        "prev_owner": "Anonymous", 
        "fav_treat": "Irish Meatballs",
        "likes": "Park Walks",
        "dislikes": "Showers",
        "previous_health_conditions": "Arthritis",
        "friendliness_level": 4, 
        "prefered_environment": "Outside Only",
        "good_for_adoption": "Yes",
        "description": "A very Irish cat, as Irish as you can get."
    },
 
    {
        "id": 12,
        "name": "Poppy",
        "image": "images/poppy.jpg",
        "breed": "Burmese",
        "age": 6,
        "gender": "Male",
        "color": "Brown, Black and White",
        "gender": "Male",
        "prev_owner": "Mello Dree", 
        "fav_treat": "Anything with a crunch",
        "likes": "The plant on the coffee table",
        "dislikes": "Loud noises",
        "previous_health_conditions": "None",
        "friendliness_level": 4, 
        "prefered_environment": "Outside Only",
        "good_for_adoption": "Yes",
        "description": "Likes to bite things, especially if it makes a crunching sound"
    },
 
    {
        "id": 13,
        "name": "Mort",
        "image": "images/mort.jpg",
        "breed": "Ragdoll",
        "age": 2,
        "color": "Black and White",
        "gender": "Female",
        "prev_owner": "Anonymous", 
        "fav_treat": "Dried Fish Flakes",
        "likes": "Rooftop",
        "dislikes": "Thunderstorms",
        "previous_health_conditions": "Diabetes",
        "friendliness_level": 5, 
        "prefered_environment": "Inside Only",
        "good_for_adoption": "No",
        "description": "Please Be sure to hold him close when there is a thunderstorm"
    },
 
    {
        "id": 14,
        "name": "Wart",
        "image": "images/wart.jpg",
        "breed": "Chartreux",
        "age": 5,
        "color": "Grey",
        "gender": "Female",
        "prev_owner": "Sean Gono", 
        "fav_treat": "Canned Tuna",
        "likes": "Treated with love and care",
        "dislikes": "Being left alone",
        "previous_health_conditions": "None",
        "friendliness_level": 5, 
        "prefered_environment": "Inside Only",
        "good_for_adoption": "Yes",
        "description": "Loving and affectionate cat, She's perfect, almost too perfect..."
    },
 
    {
        "id": 15,
        "name": "Lexi",
        "image": "images/lexi.jpg",
        "breed": "LaPerm",
        "age": 6,
        "color": "Brown",
        "gender": "Male",
        "prev_owner": "Anonymous", 
        "fav_treat": "Anything really",
        "likes": "Beaches",
        "dislikes": "Getting picked up",
        "previous_health_conditions": "Gingivitis",
        "friendliness_level": 2, 
        "prefered_environment": "Outside and Inside",
        "good_for_adoption": "Yes",
        "description": "Religously enjoyes the beaches and does not care if you get sand between her fur"
    },
 
    {
        "id": 16,
        "name": "Bob",
        "image": "images/bob.jpg",
        "breed": "Munchkin",
        "age": 1,
        "color": "Brown, Black and White",
        "gender": "Male",
        "prev_owner": "Anonymous", 
        "fav_treat": "Little bread pieces",
        "likes": "Ear scratches",
        "dislikes": "Belly rubs",
        "previous_health_conditions": "None",
        "friendliness_level": 3, 
        "prefered_environment": "Outside and Inside",
        "good_for_adoption": "Yes",
        "description": "A rescue cat that found, he seems awfully quite and shy but warms up to you eventually."
    },
 
    {
        "id": 17,
        "name": "Ratt",
        "image": "images/ratt.jpg",
        "breed": "Snowshoe",
        "age": 1,
        "color": "Brown and White",
        "gender": "Female",
        "prev_owner": "Melissa", 
        "fav_treat": "Cheesesticks",
        "likes": "Not being bullied",
        "dislikes": "Being bullied",
        "previous_health_conditions": "Fleas",
        "friendliness_level": 4, 
        "prefered_environment": "Outside and Inside",
        "good_for_adoption": "Yes",
        "description": "A rescue cat that's found near the park. Her love for cheesesticks though shows no bounds."
    },
 
    {
        "id": 18,
        "name": "Hercules",
        "image": "images/hercules.jpg",
        "breed": "Scottish Fold",
        "age": 1,
        "color": "Orange",
        "gender": "Female",
        "prev_owner": "Roxy Hudson", 
        "fav_treat": "Cat-Safe milk",
        "likes": "Sun-Bathing",
        "dislikes": "Rainy days",
        "previous_health_conditions": "None",
        "friendliness_level": 5, 
        "prefered_environment": "Outside only",
        "good_for_adoption": "No",
        "description": "Very outdoorsy and like to sleep alot in the sun."
    },
 
    {
        "id": 19,
        "name": "Satan",
        "image": "images/satan.jpg",
        "breed": "Russian White, Black, and Tabby Cat",
        "age": 5,
        "color": "Calico",
        "gender": "Female",
        "prev_owner": "Anonymous", 
        "fav_treat": "Anything meat flavoured",
        "likes": "Watching people sleep",
        "dislikes": "The voices",
        "previous_health_conditions": "None",
        "friendliness_level": 5, 
        "prefered_environment": "Inside only",
        "good_for_adoption": "Yes",
        "description": "She's an odd one, but she's still lovable all the same. Just be sure to keep her fed."
    },
 
    {
        "id": 20,
        "name": "Terry",
        "image": "images/terry.jpg",
        "breed": "Dragon Li",
        "age": 2,
        "color": "Black and White",
        "gender": "Female",
        "prev_owner": "Chen", 
        "fav_treat": "Dumpling Wrapers",
        "likes": "Sleeping",
        "dislikes": "Being surprised",
        "previous_health_conditions": "None",
        "friendliness_level": 2, 
        "prefered_environment": "Outside and Inside",
        "good_for_adoption": "Yes",
        "description": "Really enjoyes the restaurant scene, happily watching customers eat and great at pictures."
    },
 
]

def to_dict(model):
    # Pydantic v2 uses model_dump(), v1 uses dict(). Support both.
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()

#VALIDATION
validated_cats = [to_dict(Cat(**cat)) for cat in cats]
cats = validated_cats

def verify_api_key(x_api_key: Optional[str] = Header(default=None)):
    scope = API_KEYS.get(x_api_key)
    if scope is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key."
        )
    return scope

# Use as Depends(require_scope("collection")), Depends(require_scope("battle")),
# or Depends(require_scope("collection", "battle")) to accept either key.
def require_scope(*allowed_scopes: str):
    def dependency(scope: str = Depends(verify_api_key)):
        if scope not in allowed_scopes:
            raise HTTPException(
                status_code=403,
                detail="This API key isn't authorized for this endpoint."
            )
        return scope
    return dependency

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Simple Cat API",
        "version": API_VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# HOME
@app.get("/api/v1", dependencies=[Depends(require_scope("adoption", "collection", "battle", "archive"))])
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
@app.get("/api/v1/cats", dependencies=[Depends(require_scope("adoption", "collection", "battle", "archive"))])
def get_cats():
    return {
        "count": len(cats),
        "cats": cats
    }

# SEARCH CATS
@app.get("/api/v1/cats/search", dependencies=[Depends(require_scope("adoption", "collection", "battle", "archive"))])
def search_cats(q: str = Query(..., min_length=1)):
    q = q.lower()
    results = []
    for cat in cats:
        searchable_text = (
            f"{cat['name']}"
            f"{cat['breed']}"
            f"{cat['color']}"
            f"{cat['gender']}"
            f"{cat['breed']}"
            f"{cat['prefered_environment']}"
            f"{cat.get('country', '')}"
            f"{cat.get('submitted_by', cat['prev_owner'])}"
        ).lower()

        if q in searchable_text:
            results.append(cat)

    return {
        "query": q,
        "count": len(results),
        "results": results
    }


# GET ONE CAT
@app.get("/api/v1/cats/{cat_id}", dependencies=[Depends(require_scope("adoption", "collection", "battle", "archive"))])
def get_cat(cat_id: int):
    for cat in cats:
        if cat["id"] == cat_id:
            return cat
    raise HTTPException(
        status_code=404,
        detail="Cat not found."
    )


# ---------------------------------------------------------------------------
# CARCHIVE: SUBMIT A CAT
# ---------------------------------------------------------------------------
# Written to work on both Pydantic v1 and v2 (no ConfigDict / field_validator).
# Older routes/frontends (Cat Takers, Cat TCG) still expect the original Cat
# fields, so a submission is stored with those legacy fields filled in.
# When the database arrives, swap cats.append(...) in submit_cat for an INSERT.

ALLOWED_IMAGE_PREFIXES = (
    "https://",
    "data:image/jpeg;base64,",
    "data:image/png;base64,",
    "data:image/webp;base64,",
)

class CatSubmission(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    submitted_by: str = Field(default="Anonymous", max_length=60)
    country: str = Field(min_length=1, max_length=60)
    breed: str = Field(min_length=1, max_length=60)
    age: int = Field(gt=0, le=40)
    color: str = Field(min_length=1, max_length=60)
    gender: Literal["Male", "Female"]
    fav_treat: str = Field(default="Unknown", max_length=100)
    likes: str = Field(default="", max_length=200)
    dislikes: str = Field(default="", max_length=200)
    friendliness_level: int = Field(default=3, ge=1, le=5)
    prefered_environment: Literal["Inside Only", "Outside Only", "Outside and Inside"] = "Inside Only"
    description: str = Field(min_length=1, max_length=600)
    # Either empty, an https URL, or a small data: URL produced by the frontend.
    image: str = Field(default="", max_length=400000)


@app.post("/api/v1/cats", status_code=201, dependencies=[Depends(require_scope("archive"))])
def submit_cat(submission: CatSubmission):
    data = to_dict(submission)

    # trim whitespace on text fields (the image data URL is left untouched)
    for key, value in data.items():
        if isinstance(value, str) and key != "image":
            data[key] = value.strip()

    for key in ("name", "country", "breed", "color", "description"):
        if not data[key]:
            raise HTTPException(status_code=422, detail=f"{key} cannot be blank.")

    if not data["submitted_by"]:
        data["submitted_by"] = "Anonymous"
    if not data["fav_treat"]:
        data["fav_treat"] = "Unknown"

    if data["image"] and not data["image"].startswith(ALLOWED_IMAGE_PREFIXES):
        raise HTTPException(
            status_code=422,
            detail="image must be an https URL or a jpeg/png/webp data URL."
        )

    new_cat = {
        "id": max((c["id"] for c in cats), default=0) + 1,
        **data,
        # legacy fields so the other frontends keep working
        "prev_owner": data["submitted_by"],
        "previous_health_conditions": "None",
        "good_for_adoption": "N/A",
    }
    cats.append(new_cat)
    return new_cat
