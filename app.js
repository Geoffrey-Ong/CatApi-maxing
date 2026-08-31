const API_URL = "https://cat-api-maxingthesequel.vercel.app";

// SCROLL TO CATS SECTION
function scrollToCats() {
    document.getElementById("catsSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

// TOGGLE SHADOW ON STICKY SEARCH BAR ONCE THE HERO SCROLLS PAST IT
function initStickySearchShadow() {
    const sentinel = document.getElementById("stickySentinel");
    const searchBar = document.getElementById("searchSticky");
    if (!sentinel || !searchBar) return;

    const observer = new IntersectionObserver(
        ([entry]) => {
            searchBar.classList.toggle("stuck", !entry.isIntersecting);
        },
        { threshold: 0 }
    );

    observer.observe(sentinel);
}

initStickySearchShadow();


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
        openModal(cat);
    }
    catch (error) {
        console.error(error);
        alert("Unable to retrieve cat.");
    }

}

// OPEN MODAL
function openModal(cat) {
    document.getElementById("modalCatName").textContent = cat.name;
    document.getElementById("modalCatBreed").textContent = cat.breed;
    document.getElementById("modalCatDescription").textContent = cat.description;

    const details = [
        { label: "Age", value: cat.age ? `${cat.age} years old` : null },
        { label: "Gender", value: cat.gender },
        { label: "Color", value: cat.color },
        { label: "Previous Owner", value: cat.prev_owner },
        { label: "Favorite Treat", value: cat.fav_treat },
        { label: "Likes", value: cat.likes },
        { label: "Dislikes", value: cat.dislikes },
        { label: "Health History", value: cat.previous_health_conditions },
        { label: "Friendliness", value: cat.friendliness_level },
        { label: "Preferred Environment", value: cat.prefered_environment || cat.preferred_environment },
        { label: "Good for Adoption", value: cat.good_for_adoption },
    ];
    
    document.getElementById("modalDetailGrid").innerHTML = details
        .filter(item => item.value)
        .map(item => `
            <div class="detail-row">
                <span class="detail-label">${item.label}</span>
                <span class="detail-value">${item.value}</span>
            </div>
        `)
        .join("");
    const modal = document.getElementById("catModal");
    modal.classList.remove("closing");
    modal.classList.add("active");
}

//CLOSE MODAL
function closeModal() {
    const modal = document.getElementById("catModal");
    modal.classList.remove("active");
    modal.classList.add("closing");
 
    // wait for the fade/slide-out animation to finish
    setTimeout(() => {
        modal.classList.remove("closing");
    }, 350);
}

// CLOSE WHEN CLICKING OUTSIDE THE CARD
function handleOverlayClick(event) {
    if (event.target.id === "catModal") {
        closeModal();
    }
}

// CLOSE ON ESCAPE KEY
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        closeModal();
    }
});

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