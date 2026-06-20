(function () {
    const coachBubble = document.querySelector("#coachBubble");
    const iggyBubble = document.querySelector("#iggyBubble");
    const defaultTip = "Rico Runner here. Tap a field and I will point out what to enter.";
    const defaultIggyTip = "Iggy here. Start easy, breathe steady, and enjoy the walk.";

    function setCoachTip(message) {
        if (coachBubble) {
            coachBubble.textContent = message || defaultTip;
        }
    }

    function setIggyTip(message) {
        if (iggyBubble) {
            iggyBubble.textContent = message || defaultIggyTip;
        }
    }

    function clearHighlights() {
        document.querySelectorAll(".coach-focus").forEach((element) => {
            element.classList.remove("coach-focus");
        });
    }

    document.querySelectorAll("[data-coach-tip]").forEach((field) => {
        field.addEventListener("focus", () => {
            clearHighlights();
            field.classList.add("coach-focus");
            if (field.closest(".iggy-panel")) {
                setIggyTip(field.dataset.coachTip);
            } else {
                setCoachTip(field.dataset.coachTip);
            }
        });

        field.addEventListener("blur", () => {
            field.classList.remove("coach-focus");
        });
    });

    document.querySelectorAll("[data-prompt]").forEach((button) => {
        button.addEventListener("click", () => {
            const form = button.closest("form");
            const questionBox = form ? form.querySelector("textarea[name='question']") : null;
            if (!form || !questionBox) {
                return;
            }

            questionBox.value = button.dataset.prompt;
            questionBox.focus();
            if (form.dataset.agent === "iggy") {
                setIggyTip("Great question. Iggy will keep the walk simple and beginner-friendly.");
            } else {
                setCoachTip("Great question. I will use your saved runs to answer like your personal coqui coach.");
            }
            form.requestSubmit();
        });
    });

    function appendMessage(chatMessages, text, sender, avatarPath, coachClass) {
        if (!chatMessages || !text) {
            return;
        }

        const message = document.createElement("div");
        const paragraph = document.createElement("p");
        paragraph.textContent = text;
        message.className = `chat-message ${sender === "user" ? "user-message" : coachClass}`;

        if (sender !== "user") {
            const avatar = document.createElement("img");
            avatar.src = avatarPath;
            avatar.alt = "";
            message.appendChild(avatar);
        }

        message.appendChild(paragraph);
        chatMessages.appendChild(message);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function coachMotivation(answer, agentName) {
        const lowerAnswer = answer.toLowerCase();

        if (agentName === "iggy") {
            if (lowerAnswer.includes("breath")) {
                return "Iggy says: soft shoulders, steady steps, easy breathing.";
            }

            if (lowerAnswer.includes("tree") || lowerAnswer.includes("bird") || lowerAnswer.includes("nature")) {
                return "Iggy says: make the walk a tiny outdoor adventure.";
            }

            if (lowerAnswer.includes("stretch")) {
                return "Iggy says: gentle stretches count as training too.";
            }

            return "Iggy says: walk first, smile second, run later.";
        }

        if (lowerAnswer.includes("recovery") || lowerAnswer.includes("easy")) {
            return "Listen to your body. Smart recovery is still training.";
        }

        if (lowerAnswer.includes("progress") || lowerAnswer.includes("improv")) {
            return "That is progress. Small steps, steady rhythm.";
        }

        if (lowerAnswer.includes("next workout")) {
            return "You have a plan. Keep it safe, steady, and repeatable.";
        }

        return "I am here with you. Keep showing up one run at a time.";
    }

    async function askAgent(question, agentName) {
        const csrfToken = document.querySelector("meta[name='csrf-token']")?.content || "";
        const response = await fetch("/agent", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({ question, agent: agentName }),
        });

        if (!response.ok) {
            throw new Error("The coach could not answer right now.");
        }

        return response.json();
    }

    function setupAgentChat(formSelector, messagesSelector, bubbleSetter, fallbackTip) {
        const chatForm = document.querySelector(formSelector);
        const chatMessages = document.querySelector(messagesSelector);

        if (!chatForm) {
            return;
        }

        const questionBox = chatForm.querySelector("textarea[name='question']");
        const agentName = chatForm.dataset.agent || "rico";
        const avatarPath = chatForm.dataset.avatar || "/static/coqui-coach.svg";
        const waitingText = chatForm.dataset.waiting || "Let me check your notes...";
        const coachClass = agentName === "iggy" ? "iggy-message" : "rico-message";

        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        chatForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const question = questionBox.value.trim();
            if (!question) {
                bubbleSetter(fallbackTip);
                questionBox.focus();
                return;
            }

            appendMessage(chatMessages, question, "user", avatarPath, coachClass);
            questionBox.value = "";
            questionBox.disabled = true;
            bubbleSetter(agentName === "iggy" ? "Iggy is checking your walk plan..." : "Rico Runner is checking your run history...");
            appendMessage(chatMessages, waitingText, agentName, avatarPath, coachClass);

            try {
                const data = await askAgent(question, agentName);
                const waitingMessage = chatMessages.querySelector(".chat-message:last-child p");
                if (waitingMessage && waitingMessage.textContent === waitingText) {
                    waitingMessage.textContent = data.answer;
                } else {
                    appendMessage(chatMessages, data.answer, agentName, avatarPath, coachClass);
                }
                bubbleSetter(coachMotivation(data.answer, agentName));
                showAvatarPopup(agentName, avatarPath, data.answer);
            } catch (error) {
                appendMessage(chatMessages, "I could not answer right now. Try again after checking that you are logged in.", agentName, avatarPath, coachClass);
                bubbleSetter("Something interrupted our chat, but I am still here.");
            } finally {
                questionBox.disabled = false;
                questionBox.focus();
            }
        });
    }

    setupAgentChat("#agentChatForm", "#chatMessages", setCoachTip, "Send me a question about your pace, progress, recovery, or next workout.");
    setupAgentChat("#iggyChatForm", "#iggyMessages", setIggyTip, "Send Iggy a question about walking, breathing, stretches, or nature-count tasks.");

    const dashboardSearch = document.querySelector("#dashboardSearch");
    const clearDashboardSearch = document.querySelector("#clearDashboardSearch");
    const dashboardSearchStatus = document.querySelector("#dashboardSearchStatus");

    function normalizeSearchText(text) {
        return (text || "").toLowerCase().replace(/\s+/g, " ").trim();
    }

    function updateDashboardSearch() {
        if (!dashboardSearch) {
            return;
        }

        const query = normalizeSearchText(dashboardSearch.value);
        const searchableItems = Array.from(document.querySelectorAll("[data-search-item]"));
        let visibleCount = 0;

        searchableItems.forEach((item) => {
            const haystack = normalizeSearchText(`${item.dataset.searchText || ""} ${item.textContent || ""}`);
            const isVisible = !query || haystack.includes(query);
            item.classList.toggle("is-hidden-by-search", !isVisible);
            if (isVisible) {
                visibleCount += 1;
            }
        });

        if (dashboardSearchStatus) {
            dashboardSearchStatus.textContent = query
                ? `${visibleCount} matching item${visibleCount === 1 ? "" : "s"} on this page.`
                : "Search anything on this page.";
        }
    }

    if (dashboardSearch) {
        dashboardSearch.addEventListener("input", updateDashboardSearch);
    }

    if (clearDashboardSearch) {
        clearDashboardSearch.addEventListener("click", () => {
            dashboardSearch.value = "";
            updateDashboardSearch();
            dashboardSearch.focus();
        });
    }

    if (window.location.hash) {
        const target = document.querySelector(window.location.hash);
        if (target && target.tagName.toLowerCase() === "details") {
            target.open = true;
        }
    }

    document.querySelectorAll(".library-group").forEach((group) => {
        const slider = group.querySelector(".library-slider");
        const countLabel = group.querySelector("[data-library-count]");

        function updateLibraryCount() {
            if (!slider || !countLabel) {
                return;
            }

            const card = slider.querySelector(".library-card");
            const total = slider.querySelectorAll(".library-card").length;
            if (!card || total === 0) {
                return;
            }

            const step = card.getBoundingClientRect().width + 12;
            const current = Math.min(total, Math.max(1, Math.round(slider.scrollLeft / step) + 1));
            countLabel.textContent = `${current} / ${total}`;
        }

        if (slider) {
            slider.addEventListener("scroll", () => {
                window.requestAnimationFrame(updateLibraryCount);
            });
            updateLibraryCount();
        }

        group.querySelectorAll("[data-library-scroll]").forEach((button) => {
            button.addEventListener("click", () => {
                if (!slider) {
                    return;
                }

                const direction = button.dataset.libraryScroll === "left" ? -1 : 1;
                const card = slider.querySelector(".library-card");
                const distance = card ? card.getBoundingClientRect().width + 12 : 280;

                slider.scrollBy({
                    left: direction * distance,
                    behavior: "smooth",
                });
            });
        });
    });

    function showAvatarPopup(agentName, avatarPath, text) {
        if (!text) {
            return;
        }

        const popup = document.createElement("div");
        const avatar = document.createElement("img");
        const message = document.createElement("p");
        const shortText = text.length > 120 ? `${text.slice(0, 117)}...` : text;

        const popupClass = agentName === "iggy" ? "iggy-popup" : agentName === "luna" ? "luna-popup" : "rico-popup";
        popup.className = `avatar-popup ${popupClass}`;
        avatar.src = avatarPath;
        avatar.alt = "";
        message.textContent = shortText;

        popup.appendChild(avatar);
        popup.appendChild(message);
        document.body.appendChild(popup);

        window.setTimeout(() => {
            popup.classList.add("is-leaving");
        }, 4200);

        window.setTimeout(() => {
            popup.remove();
        }, 5000);
    }

    const startupPopups = [
        {
            agent: "rico",
            avatar: "/static/coqui-coach.svg",
            text: "Rico: Log your run and I will watch your pace, distance, mood, and next workout."
        },
        {
            agent: "iggy",
            avatar: "/static/iggy-coach.svg",
            text: "Iggy: New to running? Start with my walking checklist and breathe steady."
        },
        {
            agent: "luna",
            avatar: "/static/luna-recovery.svg",
            text: "Luna: I will quietly remind you to hydrate, stretch, breathe, and recover."
        }
    ];

    window.setTimeout(() => {
        startupPopups.forEach((popup, index) => {
            window.setTimeout(() => showAvatarPopup(popup.agent, popup.avatar, popup.text), index * 1200);
        });
    }, 1600);

    function createBurst(container, xPercent, yPercent) {
        const colors = ["#cf3f36", "#2f5fb8", "#f7d36b", "#1f7a5b", "#ffffff"];

        for (let index = 0; index < 18; index += 1) {
            const spark = document.createElement("span");
            const angle = (Math.PI * 2 * index) / 18;
            const distance = 80 + Math.random() * 40;
            spark.className = "spark";
            spark.style.left = `${xPercent}%`;
            spark.style.top = `${yPercent}%`;
            spark.style.background = colors[index % colors.length];
            spark.style.setProperty("--spark-x", `${Math.cos(angle) * distance}px`);
            spark.style.setProperty("--spark-y", `${Math.sin(angle) * distance}px`);
            container.appendChild(spark);
        }
    }

    function launchFireworks(message) {
        const container = document.querySelector("#fireworks");
        if (!container) {
            return;
        }

        container.innerHTML = "";
        container.classList.add("is-active");
        createBurst(container, 25, 28);
        createBurst(container, 50, 18);
        createBurst(container, 76, 30);
        setCoachTip(message);

        window.setTimeout(() => {
            container.classList.remove("is-active");
            container.innerHTML = "";
        }, 1600);
    }

    function addCelebrationPieces(container, className, count) {
        for (let index = 0; index < count; index += 1) {
            const piece = document.createElement("span");
            piece.className = className;
            piece.style.left = `${Math.random() * 100}%`;
            piece.style.animationDelay = `${Math.random() * 1.2}s`;
            piece.style.setProperty("--drift", `${-40 + Math.random() * 80}px`);
            container.appendChild(piece);
        }
    }

    function playWhistle() {
        const AudioContext = window.AudioContext || window.webkitAudioContext;

        if (!AudioContext) {
            return;
        }

        const audioContext = new AudioContext();
        const gain = audioContext.createGain();
        gain.gain.setValueAtTime(0.0001, audioContext.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.2, audioContext.currentTime + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.0001, audioContext.currentTime + 0.5);
        gain.connect(audioContext.destination);

        [0, 0.12].forEach((offset) => {
            const oscillator = audioContext.createOscillator();
            oscillator.type = "square";
            oscillator.frequency.setValueAtTime(1800, audioContext.currentTime + offset);
            oscillator.frequency.exponentialRampToValueAtTime(2600, audioContext.currentTime + offset + 0.12);
            oscillator.connect(gain);
            oscillator.start(audioContext.currentTime + offset);
            oscillator.stop(audioContext.currentTime + offset + 0.18);
        });
    }

    function launchRaceStart() {
        const overlay = document.querySelector("#raceStartOverlay");
        const phrase = document.querySelector("#racePhrase");
        const number = document.querySelector("#countdownNumber");

        if (!overlay || !phrase || !number) {
            return;
        }

        overlay.classList.add("is-active");
        overlay.querySelectorAll(".confetti-piece, .balloon-piece, .glitter-piece").forEach((piece) => {
            piece.remove();
        });
        addCelebrationPieces(overlay, "confetti-piece", 80);
        addCelebrationPieces(overlay, "balloon-piece", 16);
        addCelebrationPieces(overlay, "glitter-piece", 70);

        const sequence = [
            { count: "3", text: "On your mark" },
            { count: "2", text: "Get Set" },
            { count: "1", text: "Go!" },
        ];

        sequence.forEach((step, index) => {
            window.setTimeout(() => {
                number.textContent = step.count;
                phrase.textContent = step.text;
            }, index * 1000);
        });

        window.setTimeout(() => {
            playWhistle();
            phrase.textContent = "On your mark, Get Set, Go!";
            number.textContent = "Go!";
            setCoachTip("Rico blew the whistle. Time to build the next healthy mile.");
        }, 3000);

        window.setTimeout(() => {
            overlay.classList.remove("is-active");
            overlay.querySelectorAll(".confetti-piece, .balloon-piece, .glitter-piece").forEach((piece) => {
                piece.remove();
            });
        }, 5200);
    }

    const celebration = document.body.dataset.celebrate;
    if (document.body.dataset.welcome === "race-start") {
        launchRaceStart();
    }

    if (celebration === "run-saved") {
        launchFireworks("Goal logged. Nice work! I saved the run and updated your coaching history.");
    }

    if (celebration === "import-success") {
        launchFireworks("Workout history imported. More data means smarter coaching.");
    }
})();
