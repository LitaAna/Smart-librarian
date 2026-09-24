const messagesEl = document.getElementById("messages");
const composer = document.getElementById("composer");
const input = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const micBtn = document.getElementById("micBtn");
const statusStamp = document.getElementById("statusStamp");

const shelfEmpty = document.getElementById("shelfEmpty");
const bookCard = document.getElementById("bookCard");
const bookTitle = document.getElementById("bookTitle");
const bookSummary = document.getElementById("bookSummary");

const coverArea = document.getElementById("coverArea");
const bookCover = document.getElementById("bookCover");
const coverBtn = document.getElementById("coverBtn");

const listenBtn = document.getElementById("listenBtn");
const ttsAudio = document.getElementById("ttsAudio");

const profileButton = document.getElementById("profileButton");
const profileMenu = document.getElementById("profileMenu");

let history = [];
let currentBook = null;

let currentAudioUrl = null;
let audioIsLoading = false;
let coverIsLoading = false;


/* =========================
   Profile menu
========================= */

profileButton.addEventListener("click", () => {
  const willOpen = profileMenu.hidden;

  profileMenu.hidden = !willOpen;
  profileButton.setAttribute(
    "aria-expanded",
    String(willOpen)
  );
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".profile-wrap")) {
    profileMenu.hidden = true;
    profileButton.setAttribute(
      "aria-expanded",
      "false"
    );
  }
});


/* =========================
   UI helpers
========================= */

function addMessage(role, text) {
  const box = document.createElement("div");

  box.className = `message ${
    role === "user"
      ? "user-message"
      : "assistant-message"
  }`;

  const label = document.createElement("div");
  label.className = "message-label";

  label.textContent =
    role === "user"
      ? "You"
      : "Librarian";

  const paragraph = document.createElement("p");
  paragraph.textContent = text;

  box.append(label, paragraph);
  messagesEl.appendChild(box);

  messagesEl.scrollTop =
    messagesEl.scrollHeight;
}


function addThinking() {
  removeThinking();

  const box = document.createElement("div");

  box.className =
    "message assistant-message thinking";

  box.id = "thinkingMsg";

  box.innerHTML =
    "<span></span><span></span><span></span>";

  messagesEl.appendChild(box);

  messagesEl.scrollTop =
    messagesEl.scrollHeight;
}


function removeThinking() {
  document
    .getElementById("thinkingMsg")
    ?.remove();
}


function setStatus(text, ok = true) {
  statusStamp.innerHTML =
    `<span class="dot"></span> ${text}`;

  statusStamp.style.color =
    ok ? "" : "#a4473d";
}


function setListenButtonText(text) {
  const label =
    listenBtn.querySelector("span");

  if (label) {
    label.textContent = text;
  }
}


/* =========================
   Audio helpers
========================= */

function resetAudio() {
  ttsAudio.pause();
  ttsAudio.currentTime = 0;

  ttsAudio.removeAttribute("src");
  ttsAudio.load();

  if (currentAudioUrl) {
    URL.revokeObjectURL(
      currentAudioUrl
    );

    currentAudioUrl = null;
  }

  audioIsLoading = false;

  listenBtn.disabled = false;
  listenBtn.classList.remove("playing");

  setListenButtonText(
    "Listen to summary"
  );
}


/* =========================
   Recommendation
========================= */

function updateRecommendation(
  title,
  summary,
  coverUrl = null
) {
  resetAudio();

  currentBook = {
    title,
    summary,
    coverUrl
  };

  shelfEmpty.hidden = true;
  bookCard.hidden = false;

  bookTitle.textContent = title;
  bookSummary.textContent = summary;

  /*
    If the backend provides a cover URL,
    display it. Otherwise keep the
    cover section hidden.
  */

  if (coverUrl && coverArea && bookCover) {
    bookCover.src = coverUrl;

    bookCover.alt =
      `Cover of ${title}`;

    coverArea.hidden = false;

    bookCover.onerror = () => {
      coverArea.hidden = true;
      bookCover.removeAttribute("src");
    };
  } else if (coverArea) {
    coverArea.hidden = true;

    if (bookCover) {
      bookCover.removeAttribute("src");
    }
  }

  if (coverBtn) {
    coverBtn.disabled = false;
    coverBtn.classList.remove("loading");
    coverBtn.querySelector("span").textContent = "Generate book cover";
  }
}


if (coverBtn) {
  coverBtn.addEventListener("click", async () => {
    if (!currentBook || coverIsLoading) return;

    coverIsLoading = true;
    coverBtn.disabled = true;
    coverBtn.classList.add("loading");
    coverBtn.querySelector("span").textContent = "Generating cover...";

    try {
      const response = await fetch("/api/cover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: currentBook.title,
          summary: currentBook.summary,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not generate the book cover.");
      }

      bookCover.src = data.image;
      bookCover.alt = `Cover of ${currentBook.title}`;
      coverArea.hidden = false;
      coverBtn.querySelector("span").textContent = "Generate again";
    } catch (error) {
      addMessage("assistant", error.message || "Could not generate the book cover.");
      coverBtn.querySelector("span").textContent = "Generate book cover";
    } finally {
      coverIsLoading = false;
      coverBtn.disabled = false;
      coverBtn.classList.remove("loading");
    }
  });
}


/* =========================
   Chat
========================= */

async function sendMessage(text) {
  const cleanText = text.trim();

  if (!cleanText) {
    return;
  }

  addMessage(
    "user",
    cleanText
  );

  history.push({
    role: "user",
    content: cleanText
  });

  input.value = "";
  sendBtn.disabled = true;

  addThinking();

  try {
    const response =
      await fetch("/api/chat", {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json"
        },

        body: JSON.stringify({
          message: cleanText,
          history:
            history.slice(0, -1)
        })
      });

    const data =
      await response.json();

    removeThinking();

    if (!response.ok) {
      addMessage(
        "assistant",
        data.detail ||
          "Something went wrong."
      );

      setStatus(
        "error",
        false
      );

      return;
    }

    const reply =
      data.reply ||
      "(no response)";

    addMessage(
      "assistant",
      reply
    );

    history.push({
      role: "assistant",
      content: reply
    });

    if (
      data.book_title &&
      data.full_summary
    ) {
      updateRecommendation(
        data.book_title,
        data.full_summary,
        data.cover_url || null
      );
    }

    setStatus(
      "connected",
      true
    );

  } catch (error) {
    console.error(
      "Chat error:",
      error
    );

    removeThinking();

    addMessage(
      "assistant",
      "I couldn't contact the server. Please check that the backend is running."
    );

    setStatus(
      "disconnected",
      false
    );

  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}


composer.addEventListener(
  "submit",
  (event) => {
    event.preventDefault();

    sendMessage(
      input.value
    );
  }
);


/* =========================
   Text-to-Speech
========================= */

listenBtn.addEventListener(
  "click",
  async () => {

    if (
      !currentBook ||
      audioIsLoading
    ) {
      return;
    }

    /*
      If audio is currently playing,
      pause it.
    */

    if (
      !ttsAudio.paused &&
      !ttsAudio.ended
    ) {
      ttsAudio.pause();

      listenBtn.classList.remove(
        "playing"
      );

      setListenButtonText(
        "Continue"
      );

      return;
    }

    /*
      Resume previously generated
      audio without another API call.
    */

    if (
      ttsAudio.src &&
      ttsAudio.currentTime > 0 &&
      !ttsAudio.ended
    ) {
      try {
        await ttsAudio.play();

        listenBtn.classList.add(
          "playing"
        );

        setListenButtonText(
          "Stop"
        );

      } catch (error) {
        console.error(
          "Audio resume error:",
          error
        );

        listenBtn.classList.remove(
          "playing"
        );

        setListenButtonText(
          "Listen to summary"
        );
      }

      return;
    }

    /*
      Replay audio after it has
      finished.
    */

    if (
      ttsAudio.src &&
      ttsAudio.ended
    ) {
      ttsAudio.currentTime = 0;

      try {
        await ttsAudio.play();

        listenBtn.classList.add(
          "playing"
        );

        setListenButtonText(
          "Stop"
        );

      } catch (error) {
        console.error(
          "Audio replay error:",
          error
        );

        listenBtn.classList.remove(
          "playing"
        );

        setListenButtonText(
          "Listen to summary"
        );
      }

      return;
    }

    /*
      First click:
      generate the audio.
    */

    audioIsLoading = true;

    listenBtn.disabled = true;

    listenBtn.classList.add(
      "playing"
    );

    setListenButtonText(
      "Generating..."
    );

    try {
      const response =
        await fetch("/api/tts", {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json"
          },

          body: JSON.stringify({
            text:
              `${currentBook.title}. ${currentBook.summary}`
          })
        });

      if (!response.ok) {
        let errorMessage =
          "Audio could not be generated.";

        try {
          const errorData =
            await response.json();

          if (errorData.detail) {
            errorMessage =
              errorData.detail;
          }
        } catch {
          // Keep default message.
        }

        throw new Error(
          errorMessage
        );
      }

      const blob =
        await response.blob();

      if (currentAudioUrl) {
        URL.revokeObjectURL(
          currentAudioUrl
        );
      }

      currentAudioUrl =
        URL.createObjectURL(blob);

      ttsAudio.src =
        currentAudioUrl;

      ttsAudio.currentTime = 0;

      await ttsAudio.play();

      listenBtn.classList.add(
        "playing"
      );

      setListenButtonText(
        "Stop"
      );

    } catch (error) {
      console.error(
        "TTS error:",
        error
      );

      resetAudio();

      addMessage(
        "assistant",
        error.message ||
          "Audio could not be generated. Please check the TTS API settings."
      );

    } finally {
      audioIsLoading = false;
      listenBtn.disabled = false;
    }
  }
);


ttsAudio.addEventListener(
  "play",
  () => {
    listenBtn.classList.add(
      "playing"
    );

    setListenButtonText(
      "Stop"
    );
  }
);


ttsAudio.addEventListener(
  "pause",
  () => {
    if (
      !ttsAudio.ended &&
      ttsAudio.currentTime > 0
    ) {
      listenBtn.classList.remove(
        "playing"
      );

      setListenButtonText(
        "Continue"
      );
    }
  }
);


ttsAudio.addEventListener(
  "ended",
  () => {
    listenBtn.classList.remove(
      "playing"
    );

    setListenButtonText(
      "Listen again"
    );
  }
);


ttsAudio.addEventListener(
  "error",
  () => {
    resetAudio();

    addMessage(
      "assistant",
      "The audio file could not be played."
    );
  }
);


/* =========================
   Speech-to-Text
========================= */

let mediaRecorder = null;
let recordedChunks = [];
let isRecording = false;


micBtn.addEventListener(
  "click",
  async () => {

    if (isRecording) {
      mediaRecorder?.stop();
      return;
    }

    try {
      const stream =
        await navigator.mediaDevices
          .getUserMedia({
            audio: true
          });

      recordedChunks = [];

      mediaRecorder =
        new MediaRecorder(stream);

      mediaRecorder.addEventListener(
        "dataavailable",
        (event) => {

          if (event.data.size > 0) {
            recordedChunks.push(
              event.data
            );
          }
        }
      );

      mediaRecorder.addEventListener(
        "stop",
        async () => {

          isRecording = false;

          micBtn.classList.remove(
            "recording"
          );

          stream
            .getTracks()
            .forEach(
              (track) =>
                track.stop()
            );

          const blob =
            new Blob(
              recordedChunks,
              {
                type:
                  "audio/webm"
              }
            );

          const formData =
            new FormData();

          formData.append(
            "file",
            blob,
            "recording.webm"
          );

          input.placeholder =
            "Transcribing...";

          try {
            const response =
              await fetch(
                "/api/stt",
                {
                  method: "POST",
                  body: formData
                }
              );

            const data =
              await response.json();

            if (
              response.ok &&
              data.text
            ) {
              input.value =
                data.text;

              await sendMessage(
                data.text
              );

            } else {
              addMessage(
                "assistant",
                data.detail ||
                  "The voice message could not be transcribed."
              );
            }

          } catch (error) {
            console.error(
              "STT error:",
              error
            );

            addMessage(
              "assistant",
              "The voice message could not be transcribed."
            );

          } finally {
            input.placeholder =
              "What would you like to read?";
          }
        }
      );

      mediaRecorder.start();

      isRecording = true;

      micBtn.classList.add(
        "recording"
      );

    } catch (error) {
      console.error(
        "Microphone error:",
        error
      );

      addMessage(
        "assistant",
        "I can't access the microphone. Please check your browser permissions."
      );
    }
  }
);


/* =========================
   Health check
========================= */

fetch("/api/health")
  .then((response) => {

    if (response.ok) {
      setStatus(
        "connected",
        true
      );

    } else {
      setStatus(
        "error",
        false
      );
    }
  })

  .catch(() => {
    setStatus(
      "disconnected",
      false
    );
  });


input.focus();
