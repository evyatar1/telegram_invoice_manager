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

