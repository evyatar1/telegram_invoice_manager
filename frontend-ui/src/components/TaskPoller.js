import { useEffect } from "react";
import { fetchInvoices } from "../api";

export default function TaskPoller({ onUpdate, token }) {
  useEffect(() => {
    const iv = setInterval(async () => {
      if (!token) return;

      try {
        const data = await fetchInvoices(token);

        // Ensure onUpdate is a function
        if (typeof onUpdate === "function") {
          onUpdate(data);
        } else {
          console.error("onUpdate is not a function:", onUpdate);
        }
      } catch (error) {
        console.error("Error fetching invoices:", error);
      }
    }, 5000);

    return () => clearInterval(iv);
  }, [onUpdate, token]);

  return null;
}

















//// frontend-ui/src/components/TaskPoller.js
//import { useEffect } from "react";
//import { fetchInvoices } from "../api"; // Correct relative path from components/TaskPoller.js to api.js
//
//export default function TaskPoller({ onUpdate, token }) {
//  useEffect(() => {
//    const intervalId = setInterval(async () => {
//      // Only poll if token is available
//      if (!token) {
//        // console.log("TaskPoller: No token, skipping fetch."); // Optional: for debugging
//        return;
//      }
//
//      try {
//        const data = await fetchInvoices(token);
//        // Ensure onUpdate is a function before calling it
//        if (typeof onUpdate === "function") {
//          onUpdate(data);
//        } else {
//          // This error should ideally not be hit if onUpdate is always passed as a function
//          console.error("TaskPoller: onUpdate is not a function or is undefined:", onUpdate);
//        }
//      } catch (error) {
//        console.error("TaskPoller: Error fetching invoices:", error.response?.data?.detail || error.message);
//      }
//    }, 5000); // Poll every 5 seconds (you can adjust this)
//
//    // Cleanup function: Clear the interval when the component unmounts or dependencies change
//    return () => clearInterval(intervalId);
//  }, [onUpdate, token]); // Dependencies: Re-run effect if onUpdate or token changes
//
//  return null; // This component does not render any UI
//}





















// last version
//// polls invoice list every 5s
//import { useEffect } from "react";
//import { fetchInvoices } from "../api";
//
//export default function TaskPoller({ onUpdate, token }) {
//  useEffect(() => {
//    const iv = setInterval(async () => {
//      // It's good practice to ensure token is present before attempting to fetch
//      if (token) {
//        try {
//          const data = await fetchInvoices(token);
//          onUpdate(data);
//        } catch (error) {
//          console.error("Error fetching invoices:", error);
//          // You might want to handle this error more gracefully in the UI
//        }
//      }
//    }, 2000); // Changed from 5000 to 3000
//    return () => clearInterval(iv);
//  }, [onUpdate, token]);
//  return null;
//}
//
//





//// frontend-ui/src/components/TaskPoller.js
//import { useEffect } from "react";
//import { fetchInvoices } from "../api";
//
//export default function TaskPoller({ onUpdate, token }) {
//  useEffect(() => {
//    const iv = setInterval(async () => {
//      // It's good practice to ensure token is present before attempting to fetch
//      if (token) {
//        try {
//          const data = await fetchInvoices(token);
//          console.log("TaskPoller: Fetched invoices data:", data); // Debugging log: What fetchInvoices returns
//          onUpdate(data);
//        } catch (error) {
//          console.error("TaskPoller: Error fetching invoices:", error);
//          // You might want to handle this error more gracefully in the UI
//        }
//      } else {
//        console.log("TaskPoller: No token available, skipping invoice fetch.");
//      }
//    }, 5000); // Poll every 5 seconds
//    return () => clearInterval(iv); // Cleanup on unmount
//  }, [onUpdate, token]); // Re-run effect if onUpdate or token changes
//  return null; // This component doesn't render anything visible
//}
//
//
//
//
//
//
////// polls invoice list every 5s
////import { useEffect } from "react";
////import { fetchInvoices } from "../api"; // <-- THIS LINE IS CRUCIAL AND NEEDS TO BE ADDED
////
////export default function TaskPoller({ onUpdate, token }) {
////  useEffect(() => {
////    const iv = setInterval(async () => {
////      // It's good practice to ensure token is present before attempting to fetch
////      if (token) {
////        try {
////          const data = await fetchInvoices(token);
////          onUpdate(data);
////        } catch (error) {
////          console.error("Error fetching invoices:", error);
////          // You might want to handle this error more gracefully in the UI
////        }
////      }
////    }, 5000);
////    return () => clearInterval(iv);
////  }, [onUpdate, token]);
////  return null;
////}
