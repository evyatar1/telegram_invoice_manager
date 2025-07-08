// frontend-ui/src/App.js
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
} from "./api";
import TaskPoller from "./components/TaskPoller";
import axios from "axios";
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
ChartJS.register(ArcElement, Tooltip, Legend);

function App() {
  // State management for the entire application
  const [token, setToken] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [chartData, setChartData] = useState({});
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [view, setView] = useState("login");
  const [message, setMessage] = useState("");
  const [isSendingCsv, setIsSendingCsv] = useState(false);
  const [sendCsvMessage, setSendCsvMessage] = useState("");
  const [isSendingChart, setIsSendingChart] = useState(false);
  const [sendChartMessage, setSendChartMessage] = useState("");
  const [showConfirmModal, setShowConfirmModal] = useState(false); // State for custom confirm modal
  const [invoiceToDelete, setInvoiceToDelete] = useState(null); // State to store invoice ID for deletion
  const [selectedRowId, setSelectedRowId] = useState(null);
  // State for categories to exclude from chart
  const [excludedCategories, setExcludedCategories] = useState([]);
  // State to manage DataGrid column visibility
  const [columnVisibilityModel, setColumnVisibilityModel] = useState({});
  const fileInputRef = useRef(null);

  // Helper functions to clear messages after a delay
  const clearMessage = useCallback(() => {
    setTimeout(() => setMessage(""), 5000);
  }, []);

  const clearSendCsvMessage = useCallback(() => {
    setTimeout(() => setSendCsvMessage(""), 5000);
  }, []);

  const clearSendChartMessage = useCallback(() => {
    setTimeout(() => setSendChartMessage(""), 5000);
  }, []);

  // Custom confirmation dialog (since window.confirm is blocked in some environments)
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
        fetchUserInvoices(token); // Re-fetch invoices after deletion to update the table and chart
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


  const handleLogin = async () => {
    setMessage("");
    try {
      const { access_token } = await login(email, password);
      setToken(access_token);
      setView("dashboard");
    } catch (error) {
      setMessage(`Login failed: ${error.response?.data?.detail || error.message}`);
      clearMessage();
    }
  };

  const handleRegister = async () => {
    setMessage("");
    try {
      await registerUser(email, password, phone, telegramChatId || null);
      setMessage("Registration successful! Please verify OTP.");
      setView("verify-otp");
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
      setMessage("OTP verification successful! Redirecting to dashboard.");
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
    setTelegramChatId("");
    setView("login");
    setMessage("Logged out successfully.");
    clearMessage();
  };

  // Function to calculate chart data based on current invoices and excluded categories
  const calculateChartData = useCallback((currentInvoices, currentExcludedCategories) => {
    const filteredInvoices = currentInvoices.filter(invoice =>
      !currentExcludedCategories.includes(invoice.category || "Uncategorized")
    );

    const categories = filteredInvoices.reduce((acc, invoice) => {
      const category = invoice.category || "Uncategorized";
      acc[category] = (acc[category] || 0) + 1;
      return acc;
    }, {});

    return {
      labels: Object.keys(categories),
      datasets: [
        {
          data: Object.values(categories),
          backgroundColor: [
            "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF",
            "#FF9F40", "#6A5ACD", "#20B2AA", "#7B68EE", "#FFD700",
            "#A9A9A9", "#ADD8E6", "#8A2BE2", "#7FFF00", "#DC143C", "#00FFFF", "#00008B", "#B8860B", "#006400", "#8B008B"
          ],
          hoverBackgroundColor: [
            "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF",
            "#FF9F40", "#6A5ACD", "#20B2AA", "#7B68EE", "#FFD700",
            "#A9A9A9", "#ADD8E6", "#8A2BE2", "#7FFF00", "#DC143C", "#00FFFF", "#00008B", "#B8860B", "#006400", "#8B008B"
          ],
        },
      ],
    };
  }, []); // Dependencies for useCallback

  // Memoized fetchUserInvoices for TaskPoller's useEffect dependency
  const fetchUserInvoices = useCallback(async (userToken) => {
    if (userToken) {
      try {
        const response = await fetch("http://localhost:8000/invoices", {
          headers: {
            Authorization: `Bearer ${userToken}`,
          },
        });

        if (!response.ok) {
          throw new Error(`Error: ${response.status}`);
        }

        const data = await response.json();
        setInvoices(data);
        // Recalculate chart data based on newly fetched invoices and current excluded categories
        setChartData(calculateChartData(data, excludedCategories));
      } catch (error) {
        console.error("Failed to fetch invoices:", error);
        // Handle 401 Unauthorized specifically
        if (error.message.includes("401") || (error.response && error.response.status === 401)) {
          setMessage("Session expired or unauthorized. Please log in again.");
          setToken(null); // Clear token
          setView("login"); // Redirect to login
        } else {
          setMessage(`Failed to fetch invoices: ${error.response?.data?.detail || error.message}`);
        }
        clearMessage();
      }
    }
  }, [setInvoices, calculateChartData, excludedCategories, setMessage, clearMessage, setToken, setView]);


  useEffect(() => {
    if (token && view === "dashboard") {
      fetchUserInvoices(token);
    }
  }, [token, view, fetchUserInvoices]); // Add fetchUserInvoices to dependencies

  // Effect to update chart data when excludedCategories or invoices change
  useEffect(() => {
    setChartData(calculateChartData(invoices, excludedCategories));
  }, [excludedCategories, invoices, calculateChartData]);


  // Handle category exclusion/inclusion
  const handleCategoryToggle = (category) => {
    setExcludedCategories(prevExcluded => {
      if (prevExcluded.includes(category)) {
        return prevExcluded.filter(cat => cat !== category); // Include category (remove from excluded list)
      } else {
        return [...prevExcluded, category]; // Exclude category (add to excluded list)
      }
    });
  };
  useEffect(() => {
    const exists = invoices.some((inv) => inv.id === selectedRowId);
    if (!exists) {
      setSelectedRowId(null);
    }
  }, [invoices, selectedRowId]);

  function CustomNoRowsOverlay() {
    return (
      <GridOverlay>
        <div style={{ padding: 16, fontSize: 16, color: '#555' }}>
          No invoices to display.
        </div>
      </GridOverlay>
    );
  }

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setMessage("Uploading invoice...");
    const formData = new FormData();
    formData.append("file", file);

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
      fetchUserInvoices(token); // Pass token directly
      fileInputRef.current.value = null;
    } catch (error) {
      // Handle 401 Unauthorized specifically for upload
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

  const triggerFileInput = () => {
    fileInputRef.current.click();
  };

  const handleDownloadExcel = async () => {
    if (invoices.length === 0) {
      setMessage("No invoices to download.");
      clearMessage();
      return;
    }

    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet('Invoices');

    // Define columns for the Excel sheet
    worksheet.columns = [
      { header: 'ID', key: 'id', width: 15 }, // Changed to 'id'
      { header: 'Status', key: 'status', width: 15 },
      { header: 'Category', key: 'category', width: 20 },
      { header: 'Created At', key: 'created_at', width: 20 },
      { header: 'Vendor', key: 'vendor', width: 25 },
      { header: 'Amount', key: 'amount', width: 15 },
      { header: 'Purchase Date', key: 'purchase_date', width: 20 },
      { header: 'Original Download', key: 'download', width: 40 }
    ];

    // Add rows to the Excel sheet
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

      // Add hyperlink to the last row, last column (download)
      const rowNumber = worksheet.lastRow.number;
      const downloadCell = worksheet.getCell(`H${rowNumber}`);
      downloadCell.value = { text: 'Download', hyperlink: downloadLink };
      downloadCell.font = { color: { argb: 'FF0000FF' }, underline: true };
    });

    // Write workbook to buffer
    const buf = await workbook.xlsx.writeBuffer();

    // Create Blob and save the Excel file
    const blob = new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    saveAs(blob, 'invoices.xlsx');
    setMessage("Excel file downloaded successfully!");
    clearMessage();
  };

  const handleDownloadCSV = () => {
    if (invoices.length === 0) {
      setMessage("No invoices to download.");
      clearMessage();
      return;
    }

    // Define CSV headers
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

      // Escape quotes in CSV fields
      const escapedRow = row.map(field =>
        typeof field === "string" ? `"${field.replace(/"/g, '""')}"` : field
      );

      csvRows.push(escapedRow.join(","));
    });

    // Create CSV string and download
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
  const handleSendCsvToTelegram = async () => {
    setIsSendingCsv(true);
    setSendCsvMessage("");
    try {
      const response = await sendCsvToTelegram(token);
      setSendCsvMessage(response.message || "CSV file sent to Telegram successfully!");
      clearSendCsvMessage();
      fetchUserInvoices(token); // Pass token directly
    } catch (error) {
      // Handle 401 Unauthorized specifically
      if (error.response && error.response.status === 401) {
        setSendCsvMessage("Session expired or unauthorized. Please log in again to send CSV.");
        setToken(null);
        setView("login");
      } else {
        setSendCsvMessage(`Sending CSV to Telegram failed: ${error.response?.data?.detail || error.message}`);
      }
      clearSendCsvMessage();
    } finally {
      setIsSendingCsv(false);
    }
  };
  // Modified handleSendChartToTelegram to send excluded categories
  const handleSendChartToTelegram = async () => {
    setIsSendingChart(true);
    setSendChartMessage("");
    try {
      // Pass the excludedCategories array to the API call
      // The backend will receive this list and filter out these categories
      const response = await sendChartToTelegram(token, excludedCategories);
      setSendChartMessage(response.message || "Chart sent to Telegram successfully!");
      clearSendChartMessage();
    } catch (error) {
      // Handle 401 Unauthorized specifically
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
  // The handleDelete function uses the customConfirm modal
  const handleDelete = (invoiceId) => {
    customConfirm("Are you sure you want to delete this invoice?", invoiceId);
  };
  // DataGrid columns definition
  // Note: The 'id' field is now 'id' for display.
  // The actual 'id' (global) is still used internally for deletion.
  const columns = [
    {
      field: "id",
      headerName: "ID",
      width: 110,
      type: 'number',
      align: 'left',
      headerAlign: 'left',
      // Explicit valueGetter to ensure consistent rendering
      valueGetter: (params) => String(params.row.id || ''), // Changed to 'id'
    },
    { field: "status", headerName: "Status", width: 140 },
    { field: "category", headerName: "Category", width: 160 },
    {
      field: "created_at",
      headerName: "Created At",
      width: 180,
      valueFormatter: (params) => {
        const date = new Date(params.value);
        return date.toLocaleString();
      },
    },
    {
      field: "vendor_name",
      headerName: "Vendor",
      width: 200,
      valueGetter: (params) => params.row.extracted_data?.vendor_name || "Unknown",
    },

    {
      field: "amount",
      headerName: "Amount",
      width: 110,
      type: 'number',
      align: 'left',
      headerAlign: 'left',
      valueGetter: (params) => params.row.extracted_data?.amount || "Unknown",
    },
    {
      field: "purchase_date",
      headerName: "Purchase Date",
      width: 140,
      valueGetter: (params) => params.row.extracted_data?.purchase_date || "Unknown",
    },

    {
      field: "preview_url",
      headerName: "Original Download",
      width: 160,
      renderCell: (params) => (
        <a
          href={params.value}
          download
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline px-2 py-1 rounded-md bg-blue-100"
          style={params.value === "#" ? { pointerEvents: "none", opacity: 0.6 } : {}}
        >
          Download
        </a>
      ),
    },
    {
      field: "actions",
      headerName: "Actions",
      width: 120,
      renderCell: (params) => (
        <button
          onClick={() => handleDelete(params.row.id)}
          className="bg-red-500 text-white px-3 py-1 rounded-md hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
        >
          Delete
        </button>
      ),
    },
  ];

  const renderContent = () => {
    if (view === "login") {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100 font-sans">
          <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
            <h2 className="text-2xl font-bold mb-6 text-center text-gray-700">Login</h2>
            {message && <div className={`p-3 rounded-md mb-4 text-center ${message.includes('failed') || message.includes('Error') || message.includes('expired') || message.includes('unauthorized') ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>{message}</div>}
            <label htmlFor="email" className="mr-2 font-semibold text-gray-700">Email: </label>
            <input
              type="email"
              placeholder="Email"
              className="w-full p-3 mb-4 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <label htmlFor="password" className="mr-2 font-semibold text-gray-700 mt-2 block">Password: </label>
            <input
              type="password"
              placeholder="Password"
              className="w-full p-3 mb-6 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <label className="block mb-4">  </label>
            <button
              onClick={handleLogin}
              className="w-full bg-blue-600 text-white p-3 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              Login
            </button>
            <p className="mt-4 text-center text-gray-600">
              Don't have an account?{" "}
              <button onClick={() => setView("register")} className="text-blue-600 hover:underline">
                Register
              </button>
            </p>
          </div>
        </div>
      );
    } else if (view === "register") {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100 font-sans">
          <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
            <h2 className="text-2xl font-bold mb-6 text-center text-gray-700">Register</h2>
            {message && <div className={`p-3 rounded-md mb-4 text-center ${message.includes('failed') || message.includes('Error') ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>{message}</div>}
            <label htmlFor="email" className="mr-2 font-semibold text-gray-700">Email: </label>
            <input
              type="email"
              placeholder="Email"
              className="w-full p-3 mb-4 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <label htmlFor="password" className="mr-2 font-semibold text-gray-700 mt-2 block">Password: </label>
            <input
              type="password"
              placeholder="Password"
              className="w-full p-3 mb-4 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <label htmlFor="phone" className="mr-2 font-semibold text-gray-700 mt-2 block">Phone: </label>
            <input
              type="tel"
              placeholder="Phone (e.g., +1234567890)"
              className="w-full p-3 mb-4 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
            <label htmlFor="telegramChatId" className="mr-2 font-semibold text-gray-700 mt-2 block">Telegram Chat ID: </label>
            <input
              type="text"
              placeholder="Telegram Chat ID"
              className="w-full p-3 mb-6 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={telegramChatId}
              onChange={(e) => setTelegramChatId(e.target.value)}
            />
            <label className="block mb-4">  </label>
            <button
              onClick={handleRegister}
              className="w-full bg-green-600 text-white p-3 rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
            >
              Register
            </button>
            <p className="mt-4 text-center text-gray-600">
              Already have an account?{" "}
              <button onClick={() => setView("login")} className="text-blue-600 hover:underline">
                Login
              </button>
            </p>
          </div>
        </div>
      );
    } else if (view === "verify-otp") {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100 font-sans">
          <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
            <h2 className="text-2xl font-bold mb-6 text-center text-gray-700">Verify OTP</h2>
            {message && <div className={`p-3 rounded-md mb-4 text-center ${message.includes('failed') || message.includes('Error') ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>{message}</div>}
            <input
              type="text"
              placeholder="Enter OTP"
              className="w-full p-3 mb-6 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
            />
            <button
              onClick={handleVerifyOtp}
              className="w-full bg-purple-600 text-white p-3 rounded-md hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2"
            >
              Verify OTP
            </button>
            <p className="mt-4 text-center text-gray-600">
              Back to{" "}
              <button onClick={() => setView("login")} className="text-blue-600 hover:underline">
                Login
              </button>
            </p>
          </div>
        </div>
      );
    } else if (view === "dashboard") {
      return (
        <div className="min-h-screen bg-gray-100 p-6 font-sans">
          <header className="flex justify-between items-center bg-white p-4 rounded-lg shadow-md mb-6">
            <h1 className="text-3xl font-bold text-gray-800">Invoice Dashboard</h1>

            <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>

              <input
                type="file"
                ref={fileInputRef}
                style={{ display: "none" }}
                onChange={handleFileUpload}
                accept=".pdf,.png,.jpg,.jpeg"
              />
              <button
                onClick={triggerFileInput}
                className="bg-indigo-600 text-white px-6 py-3 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition duration-150 ease-in-out"
              >
                Upload Invoice
              </button>
              <button
                onClick={handleDownloadExcel}
                className="bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition duration-150 ease-in-out"
              >
                Download CSV
              </button>
              <button
                onClick={handleSendCsvToTelegram}
                className="bg-purple-600 text-white px-6 py-3 rounded-md hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 transition duration-150 ease-in-out"
                disabled={isSendingCsv}
              >
                {isSendingCsv ? "Sending CSV..." : "Send CSV to Telegram"}
              </button>
              <button
                onClick={handleSendChartToTelegram}
                className="bg-orange-600 text-white px-6 py-3 rounded-md hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 transition duration-150 ease-in-out"
                disabled={isSendingChart}
              >
                {isSendingChart ? "Sending Chart..." : "Send Chart to Telegram"}
              </button>
              <button
                onClick={handleLogout}
                className="bg-red-600 text-white px-6 py-3 rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition duration-150 ease-in-out"
              >
                Logout
              </button>
            </div>
          </header>

          {message && (
            <div className={`p-3 rounded-md mb-4 text-center ${message.includes('failed') || message.includes('Error') || message.includes('expired') || message.includes('unauthorized') ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>{message}</div>
          )}


                    {/* Custom Confirmation Modal */}
          {showConfirmModal && (
            <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white p-6 rounded-lg shadow-xl w-full max-w-sm">
                <h3 className="text-lg font-semibold mb-4 text-gray-800">Confirm Deletion</h3>

                <div className="flex justify-end space-x-4">
                  <button
                    onClick={handleCancelAction}
                    className="px-4 py-2 bg-gray-300 text-gray-800 rounded-md hover:bg-gray-400 focus:outline-none"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleConfirmAction}
                    className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          )}


          {sendCsvMessage && (
            <div className={`p-3 rounded-md mb-4 text-center ${sendCsvMessage.includes('Failed') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
              {sendCsvMessage}
            </div>
          )}
          {sendChartMessage && (
            <div className={`p-3 rounded-md mb-4 text-center ${sendChartMessage.includes('Failed') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
              {sendChartMessage}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div className="bg-white p-6 rounded-lg shadow-md">
              <h2 className="text-xl font-semibold mb-4 text-gray-700">Recent Invoices</h2>
              <div style={{ height: 400, width: "100%" }}>

                <DataGrid
                  rows={invoices}
                  columns={columns}
                  getRowId={(row) => row.id}
                  components={{
                    NoRowsOverlay: CustomNoRowsOverlay,
                  }}
                  pageSize={10}
                  rowsPerPageOptions={[10]}
                  density="compact"
                  className="rounded-md"
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
                  // Props for column visibility management
                  columnVisibilityModel={columnVisibilityModel}
                  onColumnVisibilityModelChange={(newModel) => setColumnVisibilityModel(newModel)}
                />

              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h2 className="text-xl font-semibold mb-4 text-gray-700">Category Summary</h2>
              {/* Category filter checkboxes */}
              <div className="flex flex-wrap gap-2 mb-4">
                {/* Get all unique categories from invoices to create checkboxes */}
                {Array.from(new Set(invoices.map(inv => inv.category || "Uncategorized"))).map(category => (
                  <label key={category} className="inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      className="form-checkbox h-5 w-5 text-indigo-600 rounded focus:ring-indigo-500"
                      checked={!excludedCategories.includes(category)} // Checked if NOT excluded
                      onChange={() => handleCategoryToggle(category)}
                    />
                    <span className="ml-2 text-gray-700 text-sm">{category}</span>
                  </label>
                ))}
              </div>
              {chartData.labels && chartData.labels.length > 0 ? (
                <div className="flex justify-center h-80">
                  <Pie data={chartData} options={{ maintainAspectRatio: false, responsive: true }} />
                </div>
              ) : (
                <p className="text-center text-gray-600">No category data available or all categories excluded from chart.</p>
              )}
            </div>
          </div>

          <TaskPoller
            token={token}
            onUpdate={() => fetchUserInvoices(token)}
          />

          {/* Custom Confirmation Modal */}
          {showConfirmModal && (
            <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white p-6 rounded-lg shadow-xl w-full max-w-sm">
                <h3 className="text-lg font-semibold mb-4 text-gray-800">Confirm Deletion</h3>
                <p className="text-gray-700 mb-6">Are you sure you want to delete this invoice?</p>
                <div className="flex justify-end space-x-4">
                  <button
                    onClick={handleCancelAction}
                    className="px-4 py-2 bg-gray-300 text-gray-800 rounded-md hover:bg-gray-400 focus:outline-none"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleConfirmAction}
                    className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      );
    }
  };
  return <>{renderContent()}</>;
}

export default App;
