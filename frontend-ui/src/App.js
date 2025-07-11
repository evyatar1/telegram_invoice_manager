import React, { useState, useEffect, useRef, useCallback } from "react";
import { DataGrid, GridOverlay } from "@mui/x-data-grid";
import { Pie } from "react-chartjs-2";
import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

import {
  login,
  fetchInvoices,
  registerUser,
  verifyOtp,
  sendCsvToTelegram,
  sendChartToTelegram,
  deleteInvoice,
  fetchUserProfile
} from "./api";
import TaskPoller from "./components/TaskPoller"; // Assuming this component exists
import axios from "axios";

import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
ChartJS.register(ArcElement, Tooltip, Legend);

// Custom overlay for DataGrid when no rows are present
function CustomNoRowsOverlay() {
  return (
    <GridOverlay>
      <div className="flex flex-col items-center justify-center h-full text-gray-500 text-lg">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H9a2 2 0 01-2-2z" />
        </svg>
        No invoices to display. Upload one to get started!
      </div>
    </GridOverlay>
  );
}

// Function to generate Excel buffer for download
const generateExcelBuffer = async (invoices) => {
  const workbook = new ExcelJS.Workbook();
  const worksheet = workbook.addWorksheet('Invoices');

  const columns = [
    { header: 'ID', key: 'id', width: 15 },
    { header: 'Status', key: 'status', width: 15 },
    { header: 'Category', key: 'category', width: 20 },
    { header: 'Created At', key: 'created_at', width: 20 },
    { header: 'Vendor', key: 'vendor', width: 25 },
    { header: 'Amount', key: 'amount', width: 15 },
    { header: 'Purchase Date', key: 'purchase_date', width: 20 },
    { header: 'Original Download', key: 'download', width: 40 }
  ];
  worksheet.columns = columns;

  invoices.forEach(invoice => {
    const extracted = invoice.extracted_data || {};
    const downloadLink = invoice.preview_url || invoice.s3_key || '';

    worksheet.addRow({
      id: invoice.id,
      status: invoice.status,
      category: invoice.category || 'Uncategorized',
      created_at: new Date(invoice.created_at).toLocaleString(),
      vendor: extracted.vendor_name || 'Unknown',
      amount: extracted.amount || 'Unknown',
      purchase_date: extracted.purchase_date || 'Unknown',
      download: 'Download'
    });

    const rowNumber = worksheet.lastRow.number;
    const downloadCell = worksheet.getCell(`H${rowNumber}`);
    downloadCell.value = { text: 'Download', hyperlink: downloadLink };
    downloadCell.font = { color: { argb: 'FF0000FF' }, underline: true };
  });
  return await workbook.xlsx.writeBuffer();
};


function App() {
  // State variables for authentication, data, and UI views
  const [token, setToken] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [chartData, setChartData] = useState({});
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [view, setView] = useState("login"); // 'login', 'register', 'telegram-link', 'dashboard'
  const [message, setMessage] = useState(""); // General purpose message display
  const [isSendingCsv, setIsSendingCsv] = useState(false);
  const [sendCsvMessage, setSendCsvMessage] = useState("");
  const [isSendingChart, setIsSendingChart] = useState(false);
  const [sendChartMessage, setSendChartMessage] = useState("");
  const [showConfirmModal, setShowConfirmModal] = useState(false); // For delete confirmation
  const [invoiceToDelete, setInvoiceToDelete] = useState(null);
  const [selectedRowId, setSelectedRowId] = useState(null);
  const [columnVisibilityModel, setColumnVisibilityModel] = useState({});
  const fileInputRef = useRef(null); // Ref for hidden file input
  const [userProfile, setUserProfile] = useState(null); // Stores user profile data

  // Callback to clear messages after a delay
  const clearMessage = useCallback(() => {
    setTimeout(() => setMessage(""), 5000);
  }, []);

  const clearSendCsvMessage = useCallback(() => {
    setTimeout(() => setSendCsvMessage(""), 5000);
  }, []);

  const clearSendChartMessage = useCallback(() => {
    setTimeout(() => setSendChartMessage(""), 5000);
  }, []);

  // Custom confirmation modal logic
  const customConfirm = (messageText, invoiceId) => {
    setMessage(messageText);
    setShowConfirmModal(true);
    setInvoiceToDelete(invoiceId);
  };

  const handleConfirmAction = async () => {
    setShowConfirmModal(false);
    setMessage(""); // Clear message immediately upon user action
    if (invoiceToDelete) {
      try {
        await deleteInvoice(invoiceToDelete, token);
        setMessage("Invoice deleted successfully!");
        setSelectedRowId(null); // Clear selection
        clearMessage();
        fetchUserInvoices(token); // Re-fetch invoices after deletion
      } catch (error) {
        setMessage(`Invoice deletion failed: ${error.response?.data?.detail || error.message}`);
      } finally {
        clearMessage();
        setInvoiceToDelete(null); // Clear the stored invoice ID
      }
    }
  };

  const handleCancelAction = () => {
    setShowConfirmModal(false);
    setMessage(""); // Clear message
    setInvoiceToDelete(null); // Clear the stored invoice ID
  };

  // Authentication handlers
  const handleLogin = async () => {
    setMessage("");
    try {
      const { access_token } = await login(email, password);
      setToken(access_token);
      const profile = await fetchUserProfile(access_token);
      setUserProfile(profile);

      if (profile.is_verified) {
        setView("dashboard");
      } else {
        setMessage("Account not verified. Please link your Telegram account to receive OTP.");
        setView("telegram-link");
      }
    } catch (error) {
      setMessage(`Login failed: ${error.response?.data?.detail || error.message}`);
      clearMessage();
    }
  };

  const handleRegister = async () => {
    setMessage("");
    try {
      await registerUser(email, password, phone);
      setMessage("Registration successful! Please link your Telegram account to verify.");
      setView("telegram-link");
      clearMessage();
    } catch (error) {
      setMessage(`Registration failed: ${error.response?.data?.detail || error.message}`);
      clearMessage();
    }
  };

  const handleVerifyOtp = async () => {
    setMessage("");
    try {
      const { access_token } = await verifyOtp(email, otp);
      setToken(access_token);
      const profile = await fetchUserProfile(access_token);
      setUserProfile(profile);

      if (profile.is_verified) {
        setMessage("OTP verification successful! Redirecting to dashboard.");
        setView("dashboard");
      } else {
        setMessage("OTP verified, but account still not fully linked. Please try linking Telegram again.");
        setView("telegram-link");
      }
      clearMessage();
    } catch (error) {
      setMessage(`OTP verification failed: ${error.response?.data?.detail || error.message}`);
      clearMessage();
    }
  };

  const handleLogout = () => {
    setToken(null);
    setInvoices([]);
    setChartData({});
    setEmail("");
    setPassword("");
    setPhone("");
    setOtp("");
    setView("login");
    setMessage("Logged out successfully.");
    clearMessage();
    setUserProfile(null);
  };

  // Calculates data for the pie chart based on invoice categories
  const calculateChartData = useCallback((currentInvoices) => {
    const categories = currentInvoices.reduce((acc, invoice) => {
      const category = invoice.category || "Uncategorized";
      // Assuming 'amount' is a numeric field for summing, if not, count instances
      const amount = parseFloat(invoice.extracted_data?.amount) || 0;
      acc[category] = (acc[category] || 0) + amount; // Summing amounts per category
      return acc;
    }, {});

    // Sort categories by amount for consistent chart rendering
    const sortedCategories = Object.entries(categories).sort(([, a], [, b]) => b - a);

    return {
      labels: sortedCategories.map(([category]) => category),
      datasets: [
        {
          data: sortedCategories.map(([, amount]) => amount),
          backgroundColor: [
            "#6366F1", "#EC4899", "#F59E0B", "#10B981", "#8B5CF6", // Tailwind-inspired colors
            "#EF4444", "#3B82F6", "#14B8A6", "#F97316", "#A855F7",
            "#22C55E", "#EAB308", "#6B7280", "#06B6D4", "#D946EF",
            "#F43F5E", "#84CC16", "#C026D3", "#FACC15", "#BE123C"
          ],
          hoverBackgroundColor: [
            "#4F46E5", "#DB2777", "#D97706", "#059669", "#7C3AED",
            "#DC2626", "#2563EB", "#0D9488", "#EA580C", "#9333EA",
            "#16A34A", "#CA8A04", "#4B5563", "#0891B2", "#C026D3",
            "#E11D48", "#65A30D", "#A21CAF", "#EAB308", "#9F1239"
          ],
          borderColor: '#ffffff', // White border for slices
          borderWidth: 2,
        },
      ],
    };
  }, []);

  // Fetches user invoices and profile data
  const fetchUserInvoices = useCallback(async (userToken) => {
    if (userToken) {
      try {
        const invoicesResponse = await fetch(`${process.env.REACT_APP_API_URL || "http://localhost:8000"}/invoices`, {
          headers: {
            Authorization: `Bearer ${userToken}`,
          },
        });
        if (!invoicesResponse.ok) {
          throw new Error(`Error fetching invoices: ${invoicesResponse.status}`);
        }
        const invoicesData = await invoicesResponse.json();
        setInvoices(invoicesData);
        setChartData(calculateChartData(invoicesData));

        const profile = await fetchUserProfile(userToken);
        setUserProfile(profile);

        // If user was on telegram-link view and now verified, redirect to dashboard
        if (profile.is_verified && view === "telegram-link") {
          setMessage("Telegram account linked and verified! Redirecting to dashboard.");
          setView("dashboard");
          clearMessage();
        }

      } catch (error) {
        console.error("Failed to fetch data:", error);
        if (error.message.includes("401") || (error.response && error.response.status === 401)) {
          setMessage("Session expired or unauthorized. Please log in again.");
          setToken(null);
          setView("login");
        } else {
          setMessage(`Failed to fetch data: ${error.response?.data?.detail || error.message}`);
        }
        clearMessage();
      }
    }
  }, [setInvoices, calculateChartData, setMessage, clearMessage, setToken, setView, fetchUserProfile, view]);

  // Effect to fetch invoices when token changes or on initial load
  useEffect(() => {
    if (token) {
      fetchUserInvoices(token);
    }
  }, [token, fetchUserInvoices]);

  // Effect to recalculate chart data when invoices change
  useEffect(() => {
    setChartData(calculateChartData(invoices));
  }, [invoices, calculateChartData]);

  // Effect to clear selected row if it no longer exists in the invoices list
  useEffect(() => {
    const exists = invoices.some((inv) => inv.id === selectedRowId);
    if (!exists) {
      setSelectedRowId(null);
    }
  }, [invoices, selectedRowId]);

  // Handles file upload for invoices
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setMessage("Uploading invoice...");
    const formData = new FormData();
    formData.append("file", file);
    // Include telegram_chat_id if available, as the API expects it now
    if (userProfile?.telegram_chat_id) {
      formData.append("telegram_chat_id", userProfile.telegram_chat_id);
    } else {
      setMessage("Telegram chat ID not found. Please link your Telegram account first.");
      clearMessage();
      return;
    }

    try {
      const response = await axios.post(
        `${process.env.REACT_APP_API_URL || "http://localhost:8000"}/upload-invoice`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
            Authorization: `Bearer ${token}`,
          },
        }
      );
      setMessage(response.data.message || "File uploaded successfully!");
      clearMessage();
      fetchUserInvoices(token); // Re-fetch data to update UI
      fileInputRef.current.value = null; // Clear file input
    } catch (error) {
      if (error.response && error.response.status === 401) {
        setMessage("Session expired or unauthorized. Please log in again to upload.");
        setToken(null);
        setView("login");
      } else {
        setMessage(`Upload failed: ${error.response?.data?.detail || error.message}`);
      }
      clearMessage();
    }
  };

  // Triggers the hidden file input click
  const triggerFileInput = () => {
    fileInputRef.current.click();
  };

  // Handles Excel download
  const handleDownloadExcel = async () => {
    if (invoices.length === 0) {
      setMessage("No invoices to download.");
      clearMessage();
      return;
    }

    const buf = await generateExcelBuffer(invoices);

    const blob = new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    saveAs(blob, 'invoices.xlsx');
    setMessage("Excel file downloaded successfully!");
    clearMessage();
  };

  // Handles CSV download (kept for completeness, though Excel is preferred)
  const handleDownloadCSV = () => {
    if (invoices.length === 0) {
      setMessage("No invoices to download.");
      clearMessage();
      return;
    }

    const headers = [
      "ID",
      "Status",
      "Category",
      "Created At",
      "Vendor",
      "Amount",
      "Purchase Date",
      "Original Download"
    ];

    const csvRows = [];
    csvRows.push(headers.join(","));

    invoices.forEach(invoice => {
      const extracted = invoice.extracted_data || {};

      const downloadLink = invoice.preview_url || invoice.s3_key || "Unknown";
      const row = [
        invoice.id,
        invoice.status,
        invoice.category || "Uncategorized",
        new Date(invoice.created_at).toLocaleString(),
        extracted.vendor_name || "Unknown",
        extracted.amount || "Unknown",
        extracted.purchase_date || "Unknown",
        downloadLink
      ];

      const escapedRow = row.map(field =>
        typeof field === "string" ? `"${field.replace(/"/g, '""')}"` : field
      );

      csvRows.push(escapedRow.join(","));
    });

    const csvString = csvRows.join("\n");
    const blob = new Blob([csvString], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "invoices.csv");
    link.style.visibility = "hidden";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setMessage("CSV file downloaded successfully!");
    clearMessage();
  };

  // Sends Excel file to Telegram
  const handleSendCsvToTelegram = async () => {
    setIsSendingCsv(true);
    setSendCsvMessage("");
    try {
      const response = await sendCsvToTelegram(token);
      setSendCsvMessage(response.message || "Excel file sent to Telegram successfully!");
      clearSendCsvMessage();
      fetchUserInvoices(token);
    } catch (error) {
      if (error.response && error.response.status === 401) {
        setSendCsvMessage("Session expired or unauthorized. Please log in again to send Excel.");
        setToken(null);
        setView("login");
      } else {
        setSendCsvMessage(`Sending Excel to Telegram failed: ${error.response?.data?.detail || error.message}`);
      }
      clearSendCsvMessage();
    } finally {
      setIsSendingCsv(false);
    }
  };

  // Sends chart image to Telegram
  const handleSendChartToTelegram = async () => {
    setIsSendingChart(true);
    setSendChartMessage("");
    try {
      // Prepare chart data for the API: total amount per category
      const categoriesSummary = chartData.labels.map((label, index) => ({
        category: label,
        total_amount: chartData.datasets[0].data[index]
      }));
      const response = await sendChartToTelegram(token, categoriesSummary);
      setSendChartMessage(response.message || "Chart sent to Telegram successfully!");
      clearSendChartMessage();
    } catch (error) {
      if (error.response && error.response.status === 401) {
        setSendChartMessage("Session expired or unauthorized. Please log in again to send chart.");
        setToken(null);
        setView("login");
      } else {
        setSendChartMessage(`Sending chart to Telegram failed: ${error.response?.data?.detail || error.message}`);
      }
      clearSendChartMessage();
    } finally {
      setIsSendingChart(false);
    }
  };

  // Triggers invoice deletion confirmation
  const handleDelete = (invoiceId) => {
    customConfirm("Are you sure you want to delete this invoice?", invoiceId);
  };

  // DataGrid column definitions
  const columns = [
    {
      field: "id",
      headerName: "ID",
      width: 90, // Adjusted width
      type: 'number',
      align: 'left',
      headerAlign: 'left',
      valueGetter: (params) => String(params.row.id || ''),
    },
    { field: "status", headerName: "Status", width: 120 }, // Adjusted width
    { field: "category", headerName: "Category", width: 150 }, // Adjusted width
    {
      field: "created_at",
      headerName: "Created At",
      width: 170, // Adjusted width
      valueFormatter: (params) => {
        const date = new Date(params.value);
        return date.toLocaleString();
      },
    },
    {
      field: "vendor_name",
      headerName: "Vendor",
      width: 180, // Adjusted width
      valueGetter: (params) => params.row.extracted_data?.vendor_name || "Unknown",
    },
    {
      field: "amount",
      headerName: "Amount",
      width: 100, // Adjusted width
      type: 'number',
      align: 'left',
      headerAlign: 'left',
      valueGetter: (params) => params.row.extracted_data?.amount || "Unknown",
    },
    {
      field: "purchase_date",
      headerName: "Purchase Date",
      width: 130, // Adjusted width
      valueGetter: (params) => params.row.extracted_data?.purchase_date || "Unknown",
    },
    {
      field: "preview_url",
      headerName: "Original", // Shorter header name
      width: 120, // Adjusted width
      renderCell: (params) => (
        <a
          href={params.value}
          download
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline px-2 py-1 rounded-md bg-blue-100 transition duration-150 ease-in-out hover:bg-blue-200"
          style={params.value === "#" ? { pointerEvents: "none", opacity: 0.6 } : {}}
        >
          Download
        </a>
      ),
    },
    {
      field: "actions",
      headerName: "Actions",
      width: 100, // Adjusted width
      renderCell: (params) => (
        <button
          onClick={() => handleDelete(params.row.id)}
          className="bg-red-500 text-white px-3 py-1 rounded-md hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition duration-150 ease-in-out"
        >
          Delete
        </button>
      ),
    },
  ];

  // Renders the appropriate UI based on the current view state
  const renderContent = () => {
    switch (view) {
      case "login":
        return (
          <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-500 to-purple-600 p-4">
            <div className="bg-white p-8 rounded-xl shadow-2xl w-full max-w-md transform transition-all duration-300 hover:scale-105">
              <h2 className="text-3xl font-extrabold mb-8 text-center text-gray-800">Welcome Back!</h2>
              {message && (
                <div className={`p-4 rounded-lg mb-6 text-center text-sm font-medium ${
                  message.includes('failed') || message.includes('Error') || message.includes('expired') || message.includes('unauthorized') || message.includes('not verified')
                    ? 'bg-red-100 text-red-700 border border-red-200'
                    : 'bg-blue-100 text-blue-700 border border-blue-200'
                } transition-all duration-300 ease-in-out`}>
                  {message}
                </div>
              )}
              <div className="mb-6">
                <label htmlFor="email" className="block text-gray-700 text-sm font-semibold mb-2">Email</label>
                <input
                  type="email"
                  placeholder="your.email@example.com"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition duration-200 ease-in-out"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="mb-8">
                <label htmlFor="password" className="block text-gray-700 text-sm font-semibold mb-2">Password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition duration-200 ease-in-out"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <button
                onClick={handleLogin}
                className="w-full bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition duration-300 ease-in-out transform hover:scale-100"
              >
                Login
              </button>
              <p className="mt-6 text-center text-gray-600 text-sm">
                Don't have an account?{" "}
                <button onClick={() => setView("register")} className="text-blue-600 font-semibold hover:underline">
                  Register here
                </button>
              </p>
            </div>
          </div>
        );

      case "register":
        return (
          <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-500 to-teal-600 p-4">
            <div className="bg-white p-8 rounded-xl shadow-2xl w-full max-w-md transform transition-all duration-300 hover:scale-105">
              <h2 className="text-3xl font-extrabold mb-8 text-center text-gray-800">Join Us!</h2>
              {message && (
                <div className={`p-4 rounded-lg mb-6 text-center text-sm font-medium ${
                  message.includes('failed') || message.includes('Error')
                    ? 'bg-red-100 text-red-700 border border-red-200'
                    : 'bg-green-100 text-green-700 border border-green-200'
                } transition-all duration-300 ease-in-out`}>
                  {message}
                </div>
              )}
              <div className="mb-6">
                <label htmlFor="email" className="block text-gray-700 text-sm font-semibold mb-2">Email</label>
                <input
                  type="email"
                  placeholder="your.email@example.com"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 transition duration-200 ease-in-out"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="mb-6">
                <label htmlFor="password" className="block text-gray-700 text-sm font-semibold mb-2">Password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 transition duration-200 ease-in-out"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <div className="mb-8">
                <label htmlFor="phone" className="block text-gray-700 text-sm font-semibold mb-2">Phone Number</label>
                <input
                  type="tel"
                  placeholder="e.g., +1234567890 (for Telegram linking)"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 transition duration-200 ease-in-out"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
              </div>
              <button
                onClick={handleRegister}
                className="w-full bg-green-600 text-white font-bold py-3 rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition duration-300 ease-in-out transform hover:scale-100"
              >
                Register
              </button>
              <p className="mt-6 text-center text-gray-600 text-sm">
                Already have an account?{" "}
                <button onClick={() => setView("login")} className="text-blue-600 font-semibold hover:underline">
                  Login
                </button>
              </p>
            </div>
          </div>
        );

      case "telegram-link":
        return (
          <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-500 to-indigo-600 p-4">
            <div className="bg-white p-8 rounded-xl shadow-2xl w-full max-w-md text-center transform transition-all duration-300 hover:scale-105">
              <h2 className="text-3xl font-extrabold mb-6 text-gray-800">Link Telegram Account</h2>
              {message && (
                <div className={`p-4 rounded-lg mb-6 text-center text-sm font-medium ${
                  message.includes('failed') || message.includes('Error')
                    ? 'bg-red-100 text-red-700 border border-red-200'
                    : 'bg-blue-100 text-blue-700 border border-blue-200'
                } transition-all duration-300 ease-in-out`}>
                  {message}
                </div>
              )}

              <p className="text-gray-700 mb-4 text-base leading-relaxed">
                To complete your registration and receive OTPs, please link your Telegram account.
              </p>
              <p className="text-gray-800 mb-6 font-semibold text-lg">
                1. Open our Telegram bot:{" "}
                <a href="https://t.me/InvoiceTelBot" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline font-bold">@InvoiceTelBot</a>{" "}
              </p>
              <p className="text-gray-800 mb-8 font-semibold text-lg">
                2. In the bot, click "Start" and then "Share My Phone Number".
                Make sure it's the same phone number you used to register here: <span className="font-extrabold text-purple-700">{phone || userProfile?.phone || 'N/A'}</span>
              </p>

              <div className="mb-8">
                <label htmlFor="otp" className="block text-gray-700 text-sm font-semibold mb-2">Enter OTP from Telegram</label>
                <input
                  type="text"
                  placeholder="••••••"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 transition duration-200 ease-in-out text-center text-lg font-mono tracking-wider"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                />
              </div>
              <button
                onClick={handleVerifyOtp}
                className="w-full bg-purple-600 text-white font-bold py-3 rounded-lg hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 transition duration-300 ease-in-out transform hover:scale-100"
              >
                Verify OTP
              </button>
              <p className="mt-6 text-center text-gray-600 text-sm">
                Back to{" "}
                <button onClick={() => setView("login")} className="text-blue-600 font-semibold hover:underline">
                  Login
                </button>
              </p>
            </div>
            {/* TaskPoller to periodically check if user is_verified */}
            {token && (
              <TaskPoller
                token={token}
                onUpdate={() => fetchUserInvoices(token)} // This will also fetch user profile and check verification
              />
            )}
          </div>
        );

      case "dashboard":
        return (
          <div className="min-h-screen bg-gray-50 p-6 sm:p-8 font-sans">
            <header className="flex flex-col sm:flex-row justify-between items-center bg-white p-4 sm:p-6 rounded-xl shadow-lg mb-6">
              <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-800 mb-4 sm:mb-0">Invoice Dashboard</h1>
              <div className="flex flex-wrap justify-center sm:justify-end items-center gap-3 sm:gap-4">
                <input
                  type="file"
                  ref={fileInputRef}
                  style={{ display: "none" }}
                  onChange={handleFileUpload}
                  accept=".pdf,.png,.jpg,.jpeg"
                />
                <button
                  onClick={triggerFileInput}
                  className="flex items-center px-4 py-2 sm:px-6 sm:py-3 bg-indigo-600 text-white font-semibold rounded-lg shadow-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition duration-150 ease-in-out transform hover:scale-105"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  Upload Invoice
                </button>
                <button
                  onClick={handleDownloadExcel}
                  className="flex items-center px-4 py-2 sm:px-6 sm:py-3 bg-green-600 text-white font-semibold rounded-lg shadow-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition duration-150 ease-in-out transform hover:scale-105"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l3-3m-3 3l-3-3m-3 8h12a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  Download Excel
                </button>
                <button
                  onClick={handleSendCsvToTelegram}
                  className="flex items-center px-4 py-2 sm:px-6 sm:py-3 bg-purple-600 text-white font-semibold rounded-lg shadow-md hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 transition duration-150 ease-in-out transform hover:scale-105"
                  disabled={isSendingCsv}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.24-.975M10 3.477a9.959 9.959 0 014.514 0M12 19.967V21m-4.773-4.242A12.004 12.004 0 0112 4.01C16.97 4.01 21 7.582 21 12a9.863 9.863 0 01-4.24.975" />
                  </svg>
                  {isSendingCsv ? "Sending..." : "Send Excel to Telegram"}
                </button>
                <button
                  onClick={handleSendChartToTelegram}
                  className="flex items-center px-4 py-2 sm:px-6 sm:py-3 bg-orange-600 text-white font-semibold rounded-lg shadow-md hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 transition duration-150 ease-in-out transform hover:scale-105"
                  disabled={isSendingChart}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 5h18a2 2 0 012 2v10a2 2 0 01-2 2H3a2 2 0 01-2-2V7a2 2 0 012-2z" />
                  </svg>
                  {isSendingChart ? "Sending..." : "Send Chart to Telegram"}
                </button>
                <button
                  onClick={handleLogout}
                  className="flex items-center px-4 py-2 sm:px-6 sm:py-3 bg-red-600 text-white font-semibold rounded-lg shadow-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition duration-150 ease-in-out transform hover:scale-105"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H3a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                  </svg>
                  Logout
                </button>
              </div>
            </header>

            {/* Message Display Area */}
            {message && (
              <div className={`p-4 rounded-lg mb-4 text-center font-medium ${
                message.includes('failed') || message.includes('Error') || message.includes('expired') || message.includes('unauthorized')
                  ? 'bg-red-100 text-red-700 border border-red-200'
                  : 'bg-blue-100 text-blue-700 border border-blue-200'
              } transition-all duration-300 ease-in-out`}>
                {message}
              </div>
            )}
            {sendCsvMessage && (
              <div className={`p-4 rounded-lg mb-4 text-center font-medium ${
                sendCsvMessage.includes('Failed') ? 'bg-red-100 text-red-700 border border-red-200' : 'bg-green-100 text-green-700 border border-green-200'
              } transition-all duration-300 ease-in-out`}>
                {sendCsvMessage}
              </div>
            )}
            {sendChartMessage && (
              <div className={`p-4 rounded-lg mb-4 text-center font-medium ${
                sendChartMessage.includes('Failed') ? 'bg-red-100 text-red-700 border border-red-200' : 'bg-green-100 text-green-700 border border-green-200'
              } transition-all duration-300 ease-in-out`}>
                {sendChartMessage}
              </div>
            )}

            {/* Dashboard Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
              <div className="lg:col-span-2 bg-white p-6 rounded-xl shadow-lg">
                <h2 className="text-2xl font-bold mb-4 text-gray-800">Recent Invoices</h2>
                <div style={{ height: 450, width: "100%" }}> {/* Increased height for better visibility */}
                  <DataGrid
                    rows={invoices}
                    columns={columns}
                    getRowId={(row) => row.id}
                    components={{
                      NoRowsOverlay: CustomNoRowsOverlay,
                    }}
                    pageSize={10}
                    rowsPerPageOptions={[10]}
                    density="comfortable" // Changed to comfortable for better spacing
                    className="rounded-lg shadow-inner" // Added shadow for depth
                    onRowClick={(params) => {
                      setSelectedRowId(params.id);
                    }}
                    selectionModel={selectedRowId ? [selectedRowId] : []}
                    localeText={{
                      footerRowSelected: (count) =>
                        count === 1
                          ? `Invoice with ID ${selectedRowId} selected`
                          : `${count} invoices selected`,
                    }}
                    columnVisibilityModel={columnVisibilityModel}
                    onColumnVisibilityModelChange={(newModel) => setColumnVisibilityModel(newModel)}
                    sx={{
                      '& .MuiDataGrid-columnHeaders': {
                        backgroundColor: '#f1f5f9', // Light gray header background
                        color: '#334155', // Darker text for headers
                        fontWeight: 'bold',
                        fontSize: '0.9rem',
                      },
                      '& .MuiDataGrid-cell': {
                        borderColor: '#e2e8f0', // Lighter border for cells
                      },
                      '& .MuiDataGrid-row:hover': {
                        backgroundColor: '#f8fafc', // Very light hover effect
                      },
                    }}
                  />
                </div>
              </div>
              <div className="lg:col-span-1 bg-white p-6 rounded-xl shadow-lg flex flex-col items-center justify-center">
                <h2 className="text-2xl font-bold mb-4 text-gray-800">Category Spending Summary</h2>
                {chartData.labels && chartData.labels.length > 0 ? (
                  <div className="flex justify-center items-center w-full h-80 sm:h-96"> {/* Responsive height */}
                    <Pie data={chartData} options={{ maintainAspectRatio: false, responsive: true }} />
                  </div>
                ) : (
                  <p className="text-center text-gray-600 text-lg">No category data available. Upload invoices with extracted data.</p>
                )}
              </div>
            </div>

            {/* Custom Confirmation Modal */}
            {showConfirmModal && (
              <div className="fixed inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center z-50 animate-fade-in">
                <div className="bg-white p-8 rounded-xl shadow-2xl w-full max-w-sm transform scale-100 transition-all duration-300 ease-out">
                  <h3 className="text-xl font-bold mb-4 text-gray-800 text-center">Confirm Deletion</h3>
                  <p className="text-gray-700 mb-6 text-center">Are you sure you want to delete this invoice? This action cannot be undone.</p>
                  <div className="flex justify-center space-x-4">
                    <button
                      onClick={handleCancelAction}
                      className="px-6 py-2 bg-gray-300 text-gray-800 font-semibold rounded-lg hover:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-2 transition duration-150 ease-in-out"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleConfirmAction}
                      className="px-6 py-2 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition duration-150 ease-in-out"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Task Poller for background updates */}
            {token && (
              <TaskPoller
                token={token}
                onUpdate={() => fetchUserInvoices(token)}
              />
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return <>{renderContent()}</>;
}

export default App;
