import axios from "axios";

const API = axios.create({
  baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000",
});

export const login = (email, password) =>
  API.post("/login", { email, password }).then(r => r.data);

export const registerUser = (email, password, phone, telegramChatId) =>
  API.post("/register", { email, password, phone, telegram_chat_id: telegramChatId }).then(r => r.data);

export const verifyOtp = (email, otp, telegramChatId) =>
  API.post("/verify-otp", { email, otp, telegram_chat_id: telegramChatId }).then(r => r.data);

export const fetchInvoices = (token) =>
  API.get("/invoices", {
    headers: { Authorization: `Bearer ${token}` },
  }).then(r => r.data);

export const sendCsvToTelegram = (token) =>
  API.post("/send-csv-to-telegram", {}, {
    headers: { Authorization: `Bearer ${token}` },
  }).then(r => r.data);

export const sendChartToTelegram = (token) =>
  API.post("/send-chart-to-telegram", {}, {
    headers: { Authorization: `Bearer ${token}` },
  }).then(r => r.data);

export const deleteInvoice = (invoiceId, token) =>
  API.delete(`/invoices/${invoiceId}`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then(r => r.data);
