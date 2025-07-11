import { useEffect, useRef } from 'react';
import axios from 'axios'; // Added axios import

/**
 * TaskPoller Component
 *
 * This component is responsible for periodically fetching user invoices and profile data
 * to keep the dashboard updated and check for Telegram account verification status.
 * It uses a polling mechanism with a configurable interval.
 *
 * Props:
 * - token: The user's authentication token (JWT).
 * - onUpdate: A callback function to be executed when new data is fetched.
 * This function typically triggers a re-fetch of invoices and user profile in App.js.
 * - interval: The polling interval in milliseconds (default: 5000ms).
 */
function TaskPoller({ token, onUpdate, interval = 5000 }) { // Added interval prop
  const intervalRef = useRef(null);

  useEffect(() => {
    // Clear any existing interval when the component mounts or dependencies change
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    // Start polling only if a token is available
    if (token) {
      intervalRef.current = setInterval(() => {
        // Execute the onUpdate callback to trigger data fetching in the parent component
        // The onUpdate function in App.js (fetchUserInvoices) now takes the token directly
        // and handles fetching both invoices and user profile.
        onUpdate();
      }, interval);
    }

    // Cleanup function: clear the interval when the component unmounts or token becomes null
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [token, onUpdate, interval]); // Re-run effect if token, onUpdate, or interval changes

  return null;
}

export default TaskPoller;
