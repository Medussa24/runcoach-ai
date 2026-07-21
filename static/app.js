(function () {
    const coachBubble = document.querySelector("#coachBubble");
    const iggyBubble = document.querySelector("#iggyBubble");
    const coachLibrary = document.querySelector("#coach-library");
    const motivationSection = document.querySelector(".motivation-section");
    const defaultTip = "Rico Runner here. Tap a field and I will point out what to enter.";
    const defaultIggyTip = "Iggy here. Start easy, breathe steady, and enjoy the walk.";

    if (
        coachLibrary
        && motivationSection
        && coachLibrary.parentElement === motivationSection.parentElement
    ) {
        motivationSection.before(coachLibrary);
    }

    const chartDataElement = document.querySelector("#runChartData");
    let runChartData = null;
    try {
        runChartData = chartDataElement ? JSON.parse(chartDataElement.textContent) : null;
    } catch (_error) {
        runChartData = null;
    }

    function prepareCanvas(canvas) {
        const width = Math.max(260, canvas.parentElement.clientWidth - 24);
        const height = 220;
        const pixelRatio = window.devicePixelRatio || 1;
        canvas.width = width * pixelRatio;
        canvas.height = height * pixelRatio;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        const context = canvas.getContext("2d");
        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
        return { context, width, height, padding: { top: 18, right: 16, bottom: 34, left: 42 } };
    }

    function showChartEmpty(canvas, isEmpty) {
        canvas.hidden = isEmpty;
        const emptyMessage = canvas.parentElement.querySelector(".chart-empty");
        if (emptyMessage) {
            emptyMessage.hidden = !isEmpty;
        }
    }

    function drawChartFrame(chart, labels, minValue, maxValue, formatter) {
        const { context, width, height, padding } = chart;
        const plotWidth = width - padding.left - padding.right;
        const plotHeight = height - padding.top - padding.bottom;
        context.clearRect(0, 0, width, height);
        context.font = "11px Segoe UI, sans-serif";
        context.fillStyle = "#687083";
        context.strokeStyle = "rgba(9, 38, 58, 0.10)";
        context.lineWidth = 1;

        [0, 0.5, 1].forEach((ratio) => {
            const y = padding.top + plotHeight * ratio;
            context.beginPath();
            context.moveTo(padding.left, y);
            context.lineTo(width - padding.right, y);
            context.stroke();
            const value = maxValue - (maxValue - minValue) * ratio;
            context.fillText(formatter(value), 2, y + 4);
        });

        if (labels.length) {
            context.fillText(labels[0].slice(5), padding.left, height - 8);
            const lastLabel = labels[labels.length - 1].slice(5);
            const textWidth = context.measureText(lastLabel).width;
            context.fillText(lastLabel, width - padding.right - textWidth, height - 8);
        }
        return { plotWidth, plotHeight };
    }

    function drawLineChart(canvas, labels, values, color, formatter = (value) => value.toFixed(1)) {
        const points = values
            .map((value, index) => ({ value, index }))
            .filter((point) => Number.isFinite(point.value));
        showChartEmpty(canvas, points.length === 0);
        if (!points.length) {
            return;
        }

        const chart = prepareCanvas(canvas);
        const numericValues = points.map((point) => point.value);
        let minValue = Math.min(...numericValues);
        let maxValue = Math.max(...numericValues);
        if (minValue === maxValue) {
            minValue = Math.max(0, minValue - 1);
            maxValue += 1;
        }
        const { plotWidth, plotHeight } = drawChartFrame(chart, labels, minValue, maxValue, formatter);
        const xFor = (index) => chart.padding.left + (labels.length === 1 ? plotWidth / 2 : (index / (labels.length - 1)) * plotWidth);
        const yFor = (value) => chart.padding.top + ((maxValue - value) / (maxValue - minValue)) * plotHeight;

        chart.context.strokeStyle = color;
        chart.context.lineWidth = 3;
        chart.context.lineJoin = "round";
        chart.context.beginPath();
        points.forEach((point, pointIndex) => {
            const x = xFor(point.index);
            const y = yFor(point.value);
            if (pointIndex === 0) chart.context.moveTo(x, y);
            else chart.context.lineTo(x, y);
        });
        chart.context.stroke();
        points.forEach((point) => {
            chart.context.beginPath();
            chart.context.fillStyle = "#ffffff";
            chart.context.strokeStyle = color;
            chart.context.lineWidth = 3;
            chart.context.arc(xFor(point.index), yFor(point.value), 5, 0, Math.PI * 2);
            chart.context.fill();
            chart.context.stroke();
        });
    }

    function drawBarChart(canvas, labels, values, colors = ["#0f8f6b"]) {
        showChartEmpty(canvas, !values.length || values.every((value) => !value));
        if (!values.length || values.every((value) => !value)) {
            return;
        }
        const chart = prepareCanvas(canvas);
        const maxValue = Math.max(1, ...values);
        const { plotWidth, plotHeight } = drawChartFrame(chart, labels, 0, maxValue, (value) => value.toFixed(value < 10 ? 1 : 0));
        const slotWidth = plotWidth / values.length;
        values.forEach((value, index) => {
            const barHeight = (value / maxValue) * plotHeight;
            chart.context.fillStyle = colors[index % colors.length];
            chart.context.fillRect(
                chart.padding.left + index * slotWidth + slotWidth * 0.18,
                chart.padding.top + plotHeight - barHeight,
                slotWidth * 0.64,
                barHeight,
            );
        });
    }

    function drawActivityChart(canvas, labels, walks, recovery) {
        const combined = walks.map((value, index) => value + (recovery[index] || 0));
        showChartEmpty(canvas, !combined.length || combined.every((value) => !value));
        if (!combined.length || combined.every((value) => !value)) return;
        const chart = prepareCanvas(canvas);
        const maxValue = Math.max(1, ...walks, ...recovery);
        const { plotWidth, plotHeight } = drawChartFrame(chart, labels, 0, maxValue, (value) => value.toFixed(0));
        const slotWidth = plotWidth / labels.length;
        labels.forEach((_label, index) => {
            const barWidth = slotWidth * 0.28;
            [walks[index] || 0, recovery[index] || 0].forEach((value, seriesIndex) => {
                const barHeight = (value / maxValue) * plotHeight;
                chart.context.fillStyle = seriesIndex === 0 ? "#0f8f6b" : "#7b61ff";
                chart.context.fillRect(
                    chart.padding.left + index * slotWidth + slotWidth * 0.18 + seriesIndex * barWidth,
                    chart.padding.top + plotHeight - barHeight,
                    barWidth - 2,
                    barHeight,
                );
            });
        });
    }

    function renderRunCharts() {
        if (!runChartData) return;
        document.querySelectorAll("[data-run-chart]").forEach((canvas) => {
            const chartType = canvas.dataset.runChart;
            if (chartType === "distance") drawLineChart(canvas, runChartData.run_labels, runChartData.distance_miles, "#0f8f6b");
            if (chartType === "pace") drawLineChart(canvas, runChartData.run_labels, runChartData.pace_minutes, "#7b61ff", (value) => `${value.toFixed(1)}`);
            if (chartType === "weekly") drawBarChart(canvas, runChartData.week_labels, runChartData.weekly_miles, ["#4ca9ff", "#0f8f6b"]);
            if (chartType === "mood") drawLineChart(canvas, runChartData.run_labels, runChartData.mood_scores, "#ff8a2f", (value) => value.toFixed(0));
            if (chartType === "activity") drawActivityChart(canvas, runChartData.week_labels, runChartData.weekly_walks, runChartData.weekly_recovery);
            if (chartType === "history") drawLineChart(canvas, runChartData.run_labels, runChartData.distance_miles, "#0f8f6b");
        });
    }

    let chartResizeTimer;
    window.addEventListener("resize", () => {
        window.clearTimeout(chartResizeTimer);
        chartResizeTimer = window.setTimeout(renderRunCharts, 120);
    });
    renderRunCharts();

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

    function setupCoachWorkspace() {
        const workspace = document.querySelector("[data-coach-workspace]");
        if (!workspace) {
            return;
        }

        const choices = Array.from(workspace.querySelectorAll("[data-coach-choice]"));
        const form = workspace.querySelector("#coachWorkspaceForm");
        const questionBox = workspace.querySelector("#coachWorkspaceQuestion");
        const hiddenAgent = form ? form.querySelector("input[name='agent']") : null;
        const avatar = workspace.querySelector("#coachAvatar");
        const role = workspace.querySelector("#coachRole");
        const title = workspace.querySelector("#coachChatTitle");
        const greeting = workspace.querySelector("#coachGreeting");
        let selectedCoach = workspace.dataset.selectedCoach || "rico";

        function currentMessageSet() {
            return workspace.querySelector(`[data-coach-messages="${selectedCoach}"]`);
        }

        function coachClass(agentName) {
            if (agentName === "iggy") return "iggy-message";
            if (agentName === "luna") return "luna-message";
            return "rico-message";
        }

        function selectedChoice() {
            return choices.find((choice) => choice.dataset.coachChoice === selectedCoach) || choices[0];
        }

        function updateCoachUrl(agentName) {
            const url = new URL(window.location.href);
            url.searchParams.set("coach", agentName);
            window.history.replaceState({}, "", url);
        }

        function selectCoach(agentName, options = {}) {
            selectedCoach = agentName || "rico";
            workspace.dataset.selectedCoach = selectedCoach;
            const choice = selectedChoice();

            choices.forEach((button) => {
                const isSelected = button.dataset.coachChoice === selectedCoach;
                button.classList.toggle("is-selected", isSelected);
                button.setAttribute("aria-checked", isSelected ? "true" : "false");
            });

            workspace.querySelectorAll("[data-coach-messages]").forEach((set) => {
                set.classList.toggle("is-hidden", set.dataset.coachMessages !== selectedCoach);
            });

            workspace.querySelectorAll("[data-coach-prompts]").forEach((set) => {
                set.classList.toggle("is-hidden", set.dataset.coachPrompts !== selectedCoach);
            });

            if (form) form.dataset.agent = selectedCoach;
            if (hiddenAgent) hiddenAgent.value = selectedCoach;
            if (avatar) avatar.src = choice.dataset.coachAvatar;
            if (role) role.textContent = choice.dataset.coachRole;
            if (title) title.textContent = choice.dataset.coachName;
            if (greeting) greeting.textContent = choice.dataset.coachGreeting;
            currentMessageSet()?.scrollTo(0, currentMessageSet().scrollHeight);

            if (!options.skipUrl) {
                updateCoachUrl(selectedCoach);
            }
        }

        choices.forEach((button, index) => {
            button.addEventListener("click", () => selectCoach(button.dataset.coachChoice));
            button.addEventListener("keydown", (event) => {
                const direction = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 0;
                if (!direction) return;
                event.preventDefault();
                const nextIndex = (index + direction + choices.length) % choices.length;
                choices[nextIndex].focus();
                selectCoach(choices[nextIndex].dataset.coachChoice);
            });
        });

        workspace.querySelectorAll("[data-coach-prompt]").forEach((button) => {
            button.addEventListener("click", () => {
                if (!questionBox || !form) return;
                questionBox.value = button.dataset.coachPrompt;
                questionBox.focus();
                form.requestSubmit();
            });
        });

        if (form && questionBox) {
            form.addEventListener("submit", async (event) => {
                event.preventDefault();
                const question = questionBox.value.trim();
                if (!question) {
                    questionBox.focus();
                    return;
                }

                const choice = selectedChoice();
                const messageSet = currentMessageSet();
                appendMessage(messageSet, question, "user", choice.dataset.coachAvatar, coachClass(selectedCoach));
                questionBox.value = "";
                questionBox.disabled = true;
                appendMessage(messageSet, "Checking your recent training context...", selectedCoach, choice.dataset.coachAvatar, coachClass(selectedCoach));

                try {
                    const data = await askAgent(question, selectedCoach);
                    const waitingMessage = messageSet?.querySelector(".chat-message:last-child p");
                    if (waitingMessage && waitingMessage.textContent === "Checking your recent training context...") {
                        waitingMessage.textContent = data.answer;
                    } else {
                        appendMessage(messageSet, data.answer, selectedCoach, choice.dataset.coachAvatar, coachClass(selectedCoach));
                    }
                    showAvatarPopup(selectedCoach, choice.dataset.coachAvatar, data.answer);
                } catch (_error) {
                    appendMessage(messageSet, "I could not answer right now. Try again after checking that you are logged in.", selectedCoach, choice.dataset.coachAvatar, coachClass(selectedCoach));
                } finally {
                    questionBox.disabled = false;
                    questionBox.focus();
                }
            });
        }

        selectCoach(selectedCoach, { skipUrl: true });
    }

    setupCoachWorkspace();

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

        document.querySelector(".avatar-popup")?.remove();

        const popup = document.createElement("div");
        const avatar = document.createElement("img");
        const message = document.createElement("p");
        const closeButton = document.createElement("button");
        const shortText = text.length > 120 ? `${text.slice(0, 117)}...` : text;

        const popupClass = agentName === "iggy" ? "iggy-popup" : agentName === "luna" ? "luna-popup" : "rico-popup";
        popup.className = `avatar-popup ${popupClass}`;
        popup.setAttribute("role", "status");
        popup.setAttribute("aria-live", "polite");
        avatar.src = avatarPath;
        avatar.alt = "";
        message.textContent = shortText;
        closeButton.type = "button";
        closeButton.className = "avatar-popup-close";
        closeButton.setAttribute("aria-label", "Close coach advice");
        closeButton.textContent = "×";

        popup.appendChild(avatar);
        popup.appendChild(message);
        popup.appendChild(closeButton);
        document.body.appendChild(popup);

        closeButton.addEventListener("click", () => popup.remove());

        window.setTimeout(() => {
            popup.classList.add("is-leaving");
        }, 4200);

        window.setTimeout(() => {
            popup.remove();
        }, 5000);
    }

    const coachAdvice = {
        rico: [
            "Wepa! Keep today's effort controlled enough that you can train consistently tomorrow.",
            "Start easy, settle into your pace, and finish with good form instead of forcing speed.",
            "Your next strong run begins with recovery: hydrate, eat well, and respect your rest day."
        ],
        iggy: [
            "Take a gentle ten-minute walk and notice three things in nature while you breathe steadily.",
            "Small win: walk for five minutes, relax your shoulders, then decide whether to continue.",
            "Try a walk-and-talk reset today. Comfortable movement counts, even when it is brief."
        ],
        luna: [
            "Pause for water, one gentle stretch, and three slow breaths. Recovery is productive too.",
            "Name one thing your body did well today, then give it the rest it needs.",
            "Keep wellness simple: hydrate, loosen tight muscles gently, and protect your sleep tonight."
        ]
    };
    const coachAdviceIndexes = { rico: 0, iggy: 0, luna: 0 };

    function openCoachAdvice(card) {
        const agentName = card.dataset.agent;
        const advice = coachAdvice[agentName] || coachAdvice.rico;
        const adviceIndex = coachAdviceIndexes[agentName] || 0;
        showAvatarPopup(agentName, card.dataset.avatar, advice[adviceIndex]);
        coachAdviceIndexes[agentName] = (adviceIndex + 1) % advice.length;
    }

    document.querySelectorAll("[data-coach-avatar]").forEach((card) => {
        card.addEventListener("click", () => openCoachAdvice(card));
        card.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openCoachAdvice(card);
            }
        });
    });

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

    function createCelebrationAudioContext() {
        const AudioContext = window.AudioContext || window.webkitAudioContext;

        if (!AudioContext) {
            return null;
        }

        const audioContext = new AudioContext();
        if (audioContext.state === "suspended") {
            audioContext.resume().catch(() => {});
        }
        return audioContext;
    }

    function showVisualCaption(text) {
        let captionDiv = document.querySelector("#accessibility-caption");
        if (!captionDiv) {
            captionDiv = document.createElement("div");
            captionDiv.id = "accessibility-caption";
            captionDiv.style.position = "fixed";
            captionDiv.style.bottom = "20px";
            captionDiv.style.left = "50%";
            captionDiv.style.transform = "translateX(-50%)";
            captionDiv.style.backgroundColor = "rgba(0, 0, 0, 0.85)";
            captionDiv.style.color = "#fff";
            captionDiv.style.padding = "12px 24px";
            captionDiv.style.borderRadius = "24px";
            captionDiv.style.zIndex = "100000";
            captionDiv.style.fontFamily = "sans-serif";
            captionDiv.style.fontSize = "15px";
            captionDiv.style.fontWeight = "600";
            captionDiv.style.letterSpacing = "0.02em";
            captionDiv.style.textAlign = "center";
            captionDiv.style.pointerEvents = "none";
            document.body.appendChild(captionDiv);
        }
        captionDiv.textContent = text;
        captionDiv.style.display = "block";
        window.setTimeout(() => {
            captionDiv.style.display = "none";
        }, 3000);
    }

    function playStartHorn() {
        const accessibilityMode = document.body.dataset.accessibilityMode || "standard";
        if (accessibilityMode === "deaf_hoh" || accessibilityMode === "visual_coaching") {
            showVisualCaption("📯 [Sound Cue: Start horn blast triggers the race start] 📯");
        }
        if (accessibilityMode === "deaf_hoh") {
            return;
        }

        const audioContext = createCelebrationAudioContext();
        if (!audioContext) {
            return;
        }

        const gain = audioContext.createGain();
        const now = audioContext.currentTime;
        gain.gain.setValueAtTime(0.0001, now);
        gain.gain.exponentialRampToValueAtTime(0.16, now + 0.04);
        gain.gain.setValueAtTime(0.16, now + 0.38);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.72);
        gain.connect(audioContext.destination);

        [165, 247].forEach((frequency, index) => {
            const oscillator = audioContext.createOscillator();
            oscillator.type = index === 0 ? "sawtooth" : "triangle";
            oscillator.frequency.setValueAtTime(frequency, now);
            oscillator.frequency.exponentialRampToValueAtTime(frequency * 0.82, now + 0.7);
            oscillator.connect(gain);
            oscillator.start(now);
            oscillator.stop(now + 0.74);
        });

        window.setTimeout(() => audioContext.close().catch(() => {}), 900);
    }

    function playCompletionSounds() {
        const accessibilityMode = document.body.dataset.accessibilityMode || "standard";
        if (accessibilityMode === "deaf_hoh" || accessibilityMode === "visual_coaching") {
            showVisualCaption("🎵 [Sound Cue: Ascending celebration chimes play] 🎵");
        }
        if (accessibilityMode === "deaf_hoh") {
            return;
        }

        const audioContext = createCelebrationAudioContext();
        if (!audioContext) {
            return;
        }

        const now = audioContext.currentTime;
        const notes = [
            { frequency: 523.25, offset: 0, duration: 0.3, volume: 0.08 },
            { frequency: 659.25, offset: 0.2, duration: 0.34, volume: 0.08 },
            { frequency: 783.99, offset: 0.42, duration: 0.48, volume: 0.09 },
            { frequency: 1200, offset: 0.95, duration: 0.12, volume: 0.06 },
            { frequency: 2100, offset: 1.12, duration: 0.2, volume: 0.07 },
            { frequency: 1200, offset: 1.48, duration: 0.12, volume: 0.055 },
            { frequency: 2100, offset: 1.65, duration: 0.2, volume: 0.065 },
        ];

        notes.forEach((note, noteIndex) => {
            const gain = audioContext.createGain();
            const start = now + note.offset;
            const stop = start + note.duration;
            const oscillator = audioContext.createOscillator();
            gain.gain.setValueAtTime(0.0001, start);
            gain.gain.exponentialRampToValueAtTime(note.volume, start + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, stop);
            gain.connect(audioContext.destination);

            oscillator.type = noteIndex < 3 ? "sine" : "triangle";
            oscillator.frequency.setValueAtTime(note.frequency, start);
            if (noteIndex >= 3) {
                oscillator.frequency.exponentialRampToValueAtTime(
                    note.frequency * 1.08,
                    stop,
                );
            }
            oscillator.connect(gain);
            oscillator.start(start);
            oscillator.stop(stop);
        });

        window.setTimeout(() => audioContext.close().catch(() => {}), 2200);
    }

    function launchRaceStart() {
        const overlay = document.querySelector("#raceStartOverlay");
        const phrase = document.querySelector("#racePhrase");
        const speaker = document.querySelector("#introSpeaker");
        const message = document.querySelector("#introMessage");
        const startButton = document.querySelector("#introStartButton");
        const progressDots = Array.from(document.querySelectorAll("#introProgress span"));
        const avatars = Array.from(document.querySelectorAll("[data-intro-agent]"));

        if (!overlay || !phrase || !speaker || !message || !startButton) {
            return;
        }

        overlay.classList.add("is-active");

        const introductions = [
            {
                agent: "rico",
                speaker: "Rico Runner",
                title: "Wepa! I am your running coach.",
                message: "I will help you understand pace, build consistent workouts, and celebrate every mile. Start by logging a run or asking me what to do next."
            },
            {
                agent: "iggy",
                speaker: "Iggy Walk Agent",
                title: "Hola! Small steps are welcome here.",
                message: "If running feels like too much today, I will help you begin with a gentle walk, steady breathing, and a little nature challenge outside."
            },
            {
                agent: "luna",
                speaker: "Luna Recovery",
                title: "I will help you recharge.",
                message: "Come to me for hydration, stretching, gratitude, mindfulness, and rest reminders. Recovery helps your next movement feel better."
            },
            {
                agent: "all",
                speaker: "Your RunCoach Team",
                title: "Let us get you moving.",
                message: "Choose one small action, step outside, and begin. We are here whenever you need encouragement, a plan, or a gentler reset."
            }
        ];

        startButton.addEventListener("click", () => {
            startButton.hidden = true;
            introductions.forEach((step, index) => {
                window.setTimeout(() => {
                    speaker.textContent = step.speaker;
                    phrase.textContent = step.title;
                    message.textContent = step.message;
                    progressDots.forEach((dot, dotIndex) => dot.classList.toggle("is-active", dotIndex === index));
                    avatars.forEach((avatar) => avatar.classList.toggle("is-speaking", step.agent === "all" || avatar.dataset.introAgent === step.agent));
                }, index * 2600);
            });

            window.setTimeout(() => {
                speaker.textContent = "Rico Runner";
                phrase.textContent = "You are ready!";
                message.textContent = "Pick one small action and get moving whenever you are ready.";
                avatars.forEach((avatar) => avatar.classList.add("is-speaking"));
                addCelebrationPieces(overlay, "confetti-piece", 80);
                addCelebrationPieces(overlay, "balloon-piece", 16);
                addCelebrationPieces(overlay, "glitter-piece", 70);
                playCompletionSounds();
                setCoachTip("Introduction complete. Choose one small movement and begin when you are ready.");
            }, introductions.length * 2600);

            window.setTimeout(() => {
                overlay.classList.remove("is-active");
                overlay.querySelectorAll(".confetti-piece, .balloon-piece, .glitter-piece").forEach((piece) => piece.remove());
            }, introductions.length * 2600 + 2400);
        }, { once: true });
    }

    const celebration = document.body.dataset.celebrate;
    const backToTopButton = document.querySelector("#backToTop");

    function updateBackToTopButton() {
        if (backToTopButton) {
            backToTopButton.hidden = window.scrollY < 600;
        }
    }

    if (backToTopButton) {
        window.addEventListener("scroll", updateBackToTopButton, { passive: true });
        backToTopButton.addEventListener("click", () => {
            const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
        });
        updateBackToTopButton();
    }

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
