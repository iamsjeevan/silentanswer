// Injected at build-time by dotenv-webpack
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

chrome.runtime.onInstalled.addListener(() => {
  console.log('🚀 Extension installed');
  chrome.contextMenus.create({
    id: 'getGeminiAnswer',
    title: 'Get Gemini Answer (to clipboard)',
    contexts: ['selection']
  });
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== 'getGeminiAnswer') return;
  const question = info.selectionText?.trim();
  if (!question) {
    console.error('❌ No text selected');
    return;
  }

  console.log('📖 Selected text:', question);
  const endpoint = 
    \`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=\${GEMINI_API_KEY}\`;
  console.log('🔗 Fetching from:', endpoint);

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contents:[{ parts:[{ text: question }] }] })
    });
    if (!response.ok) {
      console.error('❌ API response error', response.status, response.statusText);
      return;
    }
    const data = await response.json();
    console.log('📥 Raw API data:', data);

    const answer = data?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!answer) {
      console.error('❌ Unexpected API format');
      return;
    }
    console.log('💡 Extracted answer:', answer);

    await navigator.clipboard.writeText(answer);
    console.log('✅ Answer copied to clipboard');
  } catch (err) {
    console.error('🔥 Fetch/clipboard error:', err);
  }
});
