// background.js (Single Question + Context Workflow)

const STORAGE_KEY_QUESTION = 'gemini_current_question'; // Store object {main_question, context_snippets}

// --- Utility: Show Notification ---
function showNotification(title, message, idSuffix = Date.now()) {
  const notificationId = `gemini_builder_notification_${idSuffix}`;
  chrome.notifications.create(notificationId, {
    type: 'basic',
    iconUrl: 'images/icon48.png', // Ensure you have this icon
    title: title,
    message: message,
    priority: 1
  });
   setTimeout(() => {
       chrome.notifications.clear(notificationId);
   }, 4000); // Clear after 4 seconds
}

// --- Context Menu Setup ---
function setupContextMenu() {
  chrome.contextMenus.create({
    id: "addGeminiQuestionPart", // One ID for adding parts
    title: "Add Text to Gemini Question", // Simple title
    contexts: ["selection"]
  });
  console.log("Context menu created for adding question parts.");
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    setupContextMenu();
  });
  // Clear storage on install/update for a clean start
  chrome.storage.local.remove(STORAGE_KEY_QUESTION);
  console.log("Cleared any previous question data on install/update.");
});

// --- Context Menu Click Handler (Adds Main Question or Context) ---
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "addGeminiQuestionPart" && info.selectionText) {
    const selectedText = info.selectionText.trim();
    if (!selectedText) return;

    console.log("Adding text part:", selectedText.substring(0, 50) + "...");

    // Get current question object
    chrome.storage.local.get([STORAGE_KEY_QUESTION], (result) => {
      let questionData = result[STORAGE_KEY_QUESTION] || { main_question: null, context_snippets: [] };

      // Ensure structure is correct
      if (typeof questionData !== 'object' || questionData === null) {
           questionData = { main_question: null, context_snippets: [] };
      }
      if (!Array.isArray(questionData.context_snippets)) {
           questionData.context_snippets = [];
      }


      let notificationTitle = "";
      let notificationMessage = "";

      if (!questionData.main_question) {
        // First piece of text becomes the main question
        questionData.main_question = selectedText;
        notificationTitle = "Main Question Added";
        notificationMessage = `Set: "${selectedText.substring(0, 40)}..."\nRight-click again to add context.`;
        console.log("Set as main question.");

      } else {
        // Subsequent pieces become context
        questionData.context_snippets.push(selectedText);
        notificationTitle = "Context Added";
        notificationMessage = `Added: "${selectedText.substring(0, 40)}..."\nTotal context snippets: ${questionData.context_snippets.length}.`;
         console.log("Added as context snippet.");
      }

      // Save updated data back to storage
      chrome.storage.local.set({ [STORAGE_KEY_QUESTION]: questionData }, () => {
        if (chrome.runtime.lastError) {
          console.error("Error saving question part:", chrome.runtime.lastError);
          showNotification("Error", "Failed to save question part.");
        } else {
          console.log("Question part saved successfully.");
          showNotification(notificationTitle, notificationMessage);
        }
      });
    });
  }
});


// --- Keyboard Shortcut Handler (Processes Combined Question) ---
chrome.commands.onCommand.addListener((command) => {
  console.log(`Command received: ${command}`);

  if (command === "process_combined_question") {
    // 1. Get stored question data
    chrome.storage.local.get([STORAGE_KEY_QUESTION], (result) => {
      if (chrome.runtime.lastError) {
         console.error("Error getting question from storage:", chrome.runtime.lastError);
         showNotification("Error", "Could not retrieve question for processing.");
         return;
      }

      const questionData = result[STORAGE_KEY_QUESTION];

      // Check if there's at least a main question
      if (!questionData || !questionData.main_question) {
        console.log("No main question set to process.");
        showNotification("Gemini Helper", "Please add a main question first using the right-click menu.");
        return;
      }

      // 2. Construct the combined prompt
      let combined_prompt = `Main Question:\n${questionData.main_question}\n`;
      if (questionData.context_snippets && questionData.context_snippets.length > 0) {
          combined_prompt += "\nAdditional Context Provided:\n";
          questionData.context_snippets.forEach((snippet, index) => {
              combined_prompt += `[Context ${index + 1}]:\n${snippet}\n\n`;
          });
      }
      combined_prompt = combined_prompt.trim(); // Remove trailing newline

      console.log(`Processing combined question (${questionData.context_snippets?.length || 0} context snippets)...`);
      console.log("Combined prompt (start):", combined_prompt.substring(0, 200) + "..."); // Log combined prompt
      showNotification("Processing...", `Sending question with ${questionData.context_snippets?.length || 0} context snippets.`);

      // 3. Send to the SINGLE processing endpoint
      const serverUrl = "http://localhost:5000/process"; // Original endpoint
      const payload = { question: combined_prompt }; // Send combined text as the 'question'

      fetch(serverUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(response => {
        if (!response.ok) {
            return response.json().then(errData => {
                const message = errData?.message || `HTTP error! Status: ${response.status}`;
                const error = new Error(message);
                error.statusCode = response.status; // Add status code to error object
                throw error;
            }).catch(() => {
                 const error = new Error(`HTTP error! Status: ${response.status}`);
                 error.statusCode = response.status;
                 throw error;
            });
        }
        return response.json();
      })
      .then(data => {
        console.log("Backend processing successful:", data);
        // 4. Clear storage ONLY on success
        chrome.storage.local.remove(STORAGE_KEY_QUESTION, () => {
           if (chrome.runtime.lastError) {
               console.error("Failed to clear storage after successful processing:", chrome.runtime.lastError);
           } else {
               console.log("Cleared question data from storage.");
           }
        });
        showNotification("Success!", data.message || "Question processed and result copied.");

      })
      .catch(error => {
        console.error("Error processing combined question:", error);
        let errorMessage = error.message || "Unknown processing error.";
        // Check for specific status codes passed via the error object
        if (error.statusCode === 429) {
            errorMessage = "Rate limit hit. Please wait and try again.";
        }
        showNotification("Processing Failed", errorMessage);
        // DO NOT clear storage on failure
      });
    }); // End storage.local.get
  } // End if command matches
}); // End onCommand listener