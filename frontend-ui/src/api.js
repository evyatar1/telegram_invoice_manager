

// frontend-ui/src/api.js
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













//// frontend-ui/src/api.js
//import axios from "axios";
//
//const API = axios.create({
//  // Use REACT_APP_API_URL if defined (from docker-compose env), otherwise fallback to localhost:8000
//  baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000",
//});
//
///**
// * Handles user login.
// * @param {string} email - The user's email.
// * @param {string} password - The user's password.
// * @returns {Promise<Object>} - A promise that resolves with login data (e.g., access_token).
// */
//export const login = (email, password) =>
//  API.post("/login", { email, password }).then(r => r.data);
//
///**
// * Registers a new user.
// * @param {string} email - The user's email.
// * @param {string} password - The user's password.
// * @param {string} phone - The user's phone number.
// * @param {string} [telegramChatId] - Optional Telegram chat ID.
// * @returns {Promise<Object>} - A promise that resolves with registration status.
// */
//export const registerUser = (email, password, phone, telegramChatId) =>
//  API.post("/register", { email, password, phone, telegram_chat_id: telegramChatId }).then(r => r.data);
//
///**
// * Verifies the OTP.
// * @param {string} email - The user's email.
// * @param {string} otp - The OTP code.
// * @param {string} [telegramChatId] - Optional Telegram chat ID to link.
// * @returns {Promise<Object>} - A promise that resolves with verification status and token.
// */
//export const verifyOtp = (email, otp, telegramChatId) =>
//  API.post("/verify-otp", { email, otp, telegram_chat_id: telegramChatId }).then(r => r.data);
//
//
///**
// * Fetches the list of invoices for the authenticated user.
// * @param {string} token - The JWT access token for authentication.
// * @returns {Promise<Array>} - A promise that resolves with an array of invoice objects.
// */
//export const fetchInvoices = (token) =>
//  API.get("/invoices", {
//    headers: { Authorization: `Bearer ${token}` },
//  }).then(r => r.data);
//
///**
// * Sends the current user's invoices as a CSV file to their Telegram chat.
// * @param {string} token - The JWT access token for authentication.
// * @returns {Promise<Object>} - A promise that resolves with a success message.
// */
//export const sendCsvToTelegram = (token) =>
//  API.post("/send-csv-to-telegram", {}, {
//    headers: { Authorization: `Bearer ${token}` },
//  }).then(r => r.data);
//
///**
// * Sends a picture of the invoice category pie chart to the user's Telegram chat.
// * @param {string} token - The JWT access token for authentication.
// * @returns {Promise<Object>} - A promise that resolves with a success message.
// */
//export const sendChartToTelegram = (token) =>
//  API.post("/send-chart-to-telegram", {}, {
//    headers: { Authorization: `Bearer ${token}` },
//  }).then(r => r.data);
//
//

















//// frontend-ui/src/api.js
//import axios from "axios";
//
//const API = axios.create({
//  // Use REACT_APP_API_URL if defined (from docker-compose env), otherwise fallback to localhost:8000
//  baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000",
//});
//
///**
// * Handles user login.
// * @param {string} email - The user's email.
// * @param {string} password - The user's password.
// * @returns {Promise<Object>} - A promise that resolves with login data (e.g., access_token).
// */
//export const login = (email, password) =>
//  API.post("/login", { email, password }).then(r => r.data);
//
///**
// * Registers a new user.
// * @param {string} email - The user's email.
// * @param {string} password - The user's password.
// * @param {string} phone - The user's phone number.
// * @param {string} [telegramChatId] - Optional Telegram chat ID.
// * @returns {Promise<Object>} - A promise that resolves with registration status.
// */
//export const registerUser = (email, password, phone, telegramChatId) =>
//  API.post("/register", { email, password, phone, telegram_chat_id: telegramChatId }).then(r => r.data);
//
///**
// * Verifies the OTP.
// * @param {string} email - The user's email.
// * @param {string} otp - The OTP code.
// * @param {string} [telegramChatId] - Optional Telegram chat ID to link.
// * @returns {Promise<Object>} - A promise that resolves with verification status and token.
// */
//export const verifyOtp = (email, otp, telegramChatId) =>
//  API.post("/verify-otp", { email, otp, telegram_chat_id: telegramChatId }).then(r => r.data);
//
//
///**
// * Fetches the list of invoices for the authenticated user.
// * @param {string} token - The JWT access token for authentication.
// * @returns {Promise<Array>} - A promise that resolves with an array of invoice objects.
// */
//export const fetchInvoices = (token) =>
//  API.get("/invoices", {
//    headers: { Authorization: `Bearer ${token}` },
//  }).then(r => r.data);
//
///**
// * Sends a CSV file of invoices to the user's linked Telegram chat.
// * @param {string} token - The JWT access token for authentication.
// * @returns {Promise<Object>} - A promise that resolves with the API response message.
// */
//export const sendCsvToTelegram = (token) =>
//  API.post("/send-csv-telegram", {}, {
//    headers: { Authorization: `Bearer ${token}` },
//  }).then(r => r.data);
//



//// frontend-ui/src/api.js
//import axios from "axios";
//
//const API = axios.create({
//  // Use REACT_APP_API_URL if defined (from docker-compose env), otherwise fallback to localhost:8000
//  baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000",
//});
//
///**
// * Handles user login.
// * @param {string} email - The user's email.
// * @param {string} password - The user's password.
// * @returns {Promise<Object>} - A promise that resolves with login data (e.g., access_token).
// */
//export const login = (email, password) =>
//  API.post("/login", { email, password }).then(r => r.data);
//
///**
// * Registers a new user.
// * @param {string} email - The user's email.
// * @param {string} password - The user's password.
// * @param {string} phone - The user's phone number.
// * @param {string} [telegramChatId] - Optional Telegram chat ID.
// * @returns {Promise<Object>} - A promise that resolves with registration status.
// */
//export const registerUser = (email, password, phone, telegramChatId) =>
//  API.post("/register", { email, password, phone, telegram_chat_id: telegramChatId }).then(r => r.data);
//
///**
// * Verifies the OTP.
// * @param {string} email - The user's email.
// * @param {string} otp - The OTP code.
// * @param {string} [telegramChatId] - Optional Telegram chat ID to link.
// * @returns {Promise<Object>} - A promise that resolves with verification status and token.
// */
//export const verifyOtp = (email, otp, telegramChatId) =>
//  API.post("/verify-otp", { email, otp, telegram_chat_id: telegramChatId }).then(r => r.data);
//
//
///**
// * Fetches the list of invoices for the authenticated user.
// * @param {string} token - The JWT access token for authentication.
// * @returns {Promise<Array>} - A promise that resolves with an array of invoice objects.
// */
//export const fetchInvoices = (token) =>
//  API.get("/invoices", { headers: { Authorization: `Bearer ${token}` } }).then(r => r.data);
//
///**
// * Uploads a new invoice image.
// * @param {string} token - The JWT access token for authentication.
// * @param {File} file - The image file to upload.
// * @returns {Promise<Object>} - A promise that resolves with the upload status.
// */
//export const uploadInvoice = (token, file) => {
//  const formData = new FormData();
//  formData.append("file", file); // 'file' must match the parameter name in your FastAPI endpoint
//
//  return API.post("/upload-invoice", formData, {
//    headers: {
//      Authorization: `Bearer ${token}`,
//      "Content-Type": "multipart/form-data", // axios automatically sets this with FormData, but good to be explicit
//    },
//  }).then(r => r.data);
//};
//
//
//
////// frontend-ui/src/api.js
////import axios from "axios";
////
////const API = axios.create({
////  // Use REACT_APP_API_URL if defined (from docker-compose env), otherwise fallback to localhost:8000
////  baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000",
////});
////
/////**
//// * Handles user login.
//// * @param {string} email - The user's email.
//// * @param {string} password - The user's password.
//// * @returns {Promise<Object>} - A promise that resolves with login data (e.g., access_token).
//// */
////export const login = (email, password) =>
////  API.post("/login", { email, password }).then(r => r.data);
////
/////**
//// * Registers a new user.
//// * @param {string} email - The user's email.
//// * @param {string} password - The user's password.
//// * @param {string} phone - The user's phone number.
//// * @param {string} [telegramChatId] - Optional Telegram chat ID.
//// * @returns {Promise<Object>} - A promise that resolves with registration status.
//// */
////export const registerUser = (email, password, phone, telegramChatId) =>
////  API.post("/register", { email, password, phone, telegram_chat_id: telegramChatId }).then(r => r.data);
////
/////**
//// * Verifies the OTP.
//// * @param {string} email - The user's email.
//// * @param {string} otp - The OTP code.
//// * @param {string} [telegramChatId] - Optional Telegram chat ID to link.
//// * @returns {Promise<Object>} - A promise that resolves with verification status and token.
//// */
////export const verifyOtp = (email, otp, telegramChatId) =>
////  API.post("/verify-otp", { email, otp, telegram_chat_id: telegramChatId }).then(r => r.data);
////
////
/////**
//// * Fetches the list of invoices for the authenticated user.
//// * @param {string} token - The JWT access token for authentication.
//// * @returns {Promise<Array>} - A promise that resolves with an array of invoice objects.
//// */
////export const fetchInvoices = (token) =>
////  // Prepend "Bearer " to the token for the Authorization header as per OAuth2 standard
////  API.get("/invoices", { headers: { Authorization: `Bearer ${token}` } }).then(r => r.data);
