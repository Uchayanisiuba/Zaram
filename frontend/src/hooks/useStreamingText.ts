import { useState, useCallback } from 'react';

const useStreamingText = () => {
  const [displayedText, setDisplayedText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const startStreaming = useCallback(async (fullText: string) => {
    setIsStreaming(true);
    setDisplayedText('');

    for (let i = 0; i < fullText.length; i++) {
      const char = fullText[i];
      setDisplayedText((prev) => prev + char);

      let delay = 20; // Base speed for characters
      if (char === ',') {
        delay = 100; // Pause for commas
      } else if (char === '.') {
        delay = 250; // Longer pause for periods
      } else if (char === '\n') {
        delay = 350; // Longest pause for newlines
      }

      await new Promise((resolve) => setTimeout(resolve, delay));
    }

    setIsStreaming(false);
  }, []);

  return { displayedText, isStreaming, startStreaming };
};

export default useStreamingText;