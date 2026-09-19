/* SupplySense Nexus - Frontend Application */

document.addEventListener("DOMContentLoaded", () => {
    console.log("SupplySense Nexus frontend initialized.");

    const sections = document.querySelectorAll("section");

    sections.forEach((section) => {
        const heading = section.querySelector("h2");
        if (heading) {
            console.log(`Section loaded: ${heading.textContent}`);
        }
    });

    const statusEl = document.querySelector(".status");
    if (statusEl) {
        console.log("Project phase:", statusEl.textContent);
    }
});
