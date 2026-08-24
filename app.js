const API_URL = "https://catapimaxingfr.vercel.app";


// GET ALL CATS
async function loadCats() {
    try {
        const response = await fetch(`${API_URL}/cats`);
        const data = await response.json();
        displayCats(data.cats);
    }

    catch (error) {
        console.error(error);
        document.getElementById("catList").innerHTML = "Unable to connect to the API.";
    }
}


// DISPLAY CATS
function displayCats(cats) {
    const catList = document.getElementById("catList");

    catList.innerHTML = "";

    cats.forEach(cat => {
        const card = document.createElement("div");
        card.className = "cat-card";
        card.innerHTML = `
            <div class="cat-id">${cat.id}</div>
            <h3>${cat.name}</h3>
            <p class="cat-breed">${cat.breed}</p>
            <p>${cat.age} years old</p>
            <p>${cat.color}</p>
            <p>${cat.description}</p>
            <button onclick="viewCat(${cat.id})"> View Details</button>
        `;

        catList.appendChild(card);
    });

}

// GET ONE CAT
async function viewCat(id) {

    try {
        const response = await fetch(`${API_URL}/cats/${id}`);
        const cat = await response.json();

        alert(`
            ${cat.name}
            Breed: ${cat.breed}
            Age: ${cat.age}
            Color: ${cat.color}
            Description: ${cat.description}
        `);
    }
    catch (error) {
        console.error(error);
        alert("Unable to retrieve cat.");
    }

}

// SEARCH
async function searchCats() {

    const query = document.getElementById("searchInput").value;
    if (!query) {
        loadCats();
        return;
    }
    try {
        const response =
            await fetch(`${API_URL}/cats/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        displayCats(data.results);
    }

    catch (error) {
        console.error(error);
        alert("Search failed.");
    }
}

loadCats();