

// frontend-ui/src/App.js
import React, { useState, useEffect, useRef, useCallback } from "react";
import { DataGrid, GridOverlay  } from "@mui/x-data-grid";
import { Pie } from "react-chartjs-2";
import {
  login,
  fetchInvoices,
  registerUser,
  verifyOtp,
  sendCsvToTelegram,
  sendChartToTelegram,
  deleteInvoice, // Import the new deleteInvoice function
} from "./api"; // Ensure this path is correct: frontend-ui/src/api.js
import TaskPoller from "./components/TaskPoller"; // Ensure this path is correct: frontend-ui/src/components/TaskPoller.js
import axios from "axios";

// Import Chart.js components and register them
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
ChartJS.register(ArcElement, Tooltip, Legend);


async function fetchUserInvoices(userToken, setInvoices, setChartData, setMessage, clearMessage, setToken, setView) {
  if (!userToken) return;
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

    const categories = data.reduce((acc, invoice) => {
      const category = invoice.category || "Uncategorized";
      acc[category] = (acc[category] || 0) + 1;
      return acc;
    }, {});

    setChartData({
      labels: Object.keys(categories),
      datasets: [
        {
          data: Object.values(categories),
          backgroundColor: [
            "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF",
            "#FF9F40", "#6A5ACD", "#20B2AA", "#7B68EE", "#FFD700"
          ],
          hoverBackgroundColor: [
            "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF",
            "#FF9F40", "#6A5ACD", "#20B2AA", "#7B68EE", "#FFD700"
          ],
        },
      ],
    });

  } catch (error) {
    console.error("Failed to fetch invoices:", error);
    setMessage(`Failed to fetch invoices: ${error.message}`);
    clearMessage();

    if (error.message.includes("401")) {
      setToken(null);
      setView("login");
    }
  }
}




function App() {
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

  const fileInputRef = useRef(null);




  // Helper functions to clear messages after a delay
  const clearMessage = () => {
    setTimeout(() => setMessage(""), 5000);
  };

  const clearSendCsvMessage = () => {
    setTimeout(() => setSendCsvMessage(""), 5000);
  };

  const clearSendChartMessage = () => {
    setTimeout(() => setSendChartMessage(""), 5000);
  };

  // Custom confirmation dialog (since window.confirm is blocked in some environments)
  const customConfirm = (messageText, invoiceId) => {
    setMessage(messageText);
    setShowConfirmModal(true);
    // Store the action to perform on confirmation (e.g., the invoice ID for deletion)
    //setInvoiceToDelete(onConfirmAction);
    setInvoiceToDelete(invoiceId);
  };

  const handleConfirmAction = async () => {
    setShowConfirmModal(false);
    setMessage(""); // Clear message immediately upon user action
    if (invoiceToDelete) {
      try {
        await deleteInvoice(invoiceToDelete, token);
        setMessage("Invoice deleted successfully!");
        await fetchUserInvoices(token, setInvoices, setChartData, setMessage, clearMessage, setToken, setView);
      } catch (error) {
        setMessage(`Failed to delete invoice: ${error.response?.data?.detail || error.message}`);
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
      setMessage("OTP verified successfully! Redirecting to dashboard.");
      setView("dashboard");
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


  useEffect(() => {
    if (token && view === "dashboard") {
      fetchUserInvoices(token, setInvoices, setChartData, setMessage, clearMessage, setToken, setView);
    }
  }, [token, view]);


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
      fetchUserInvoices(token, setInvoices, setChartData, setMessage, clearMessage, setToken, setView);
      fileInputRef.current.value = null;
    } catch (error) {
      setMessage(`Upload failed: ${error.response?.data?.detail || error.message}`);
      clearMessage();
    }
  };

  const triggerFileInput = () => {
    fileInputRef.current.click();
  };

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
    "Download Original"
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
      invoice.created_at,
      extracted.vendor_name || "Unknown",
      extracted.amount || "Unknown",
      extracted.purchase_date || "Unknown",
      downloadLink
    ];

    // Escape quotes
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
};



  const handleSendCsvToTelegram = async () => {
    setIsSendingCsv(true);
    setSendCsvMessage("");
    try {
      const response = await sendCsvToTelegram(token);
      setSendCsvMessage(response.message || "CSV sent to Telegram successfully!");
      clearSendCsvMessage();
      fetchUserInvoices(token, setInvoices, setChartData, setMessage, clearMessage, setToken, setView);
    } catch (error) {
      setSendCsvMessage(`Failed to send CSV to Telegram: ${error.response?.data?.detail || error.message}`);
      clearSendCsvMessage();
    } finally {
      setIsSendingCsv(false);
    }
  };

  const handleSendChartToTelegram = async () => {
    setIsSendingChart(true);
    setSendChartMessage("");
    try {
      const response = await sendChartToTelegram(token);
      setSendChartMessage(response.message || "Chart sent to Telegram successfully!");
      clearSendChartMessage();
    } catch (error) {
      setSendChartMessage(`Failed to send chart to Telegram: ${error.response?.data?.detail || error.message}`);
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
  const columns = [
    { field: "id", headerName: "ID", width: 80 },
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
      width: 100,
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
      headerName: "Download Original",
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
            {message && <div className="bg-red-100 text-red-700 p-3 rounded-md mb-4">{message}</div>}
            <label htmlFor="email" className="mr-2 font-semibold text-gray-700">Email: </label>
            <input
              type="email"
              placeholder="Email"
              className="w-full p-3 mb-4 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <label htmlFor="password" className="mr-2 font-semibold text-gray-700 mt-2 block">  Password: </label>
            <input
              type="password"
              placeholder="Password"
              className="w-full p-3 mb-6 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
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
            {message && <div className="bg-blue-100 text-blue-700 p-3 rounded-md mb-4">{message}</div>}
            <label htmlFor="email" className="mr-2 font-semibold text-gray-700">Email: </label>
            <input
              type="email"
              placeholder="Email"
              className="w-full p-3 mb-4 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <label htmlFor="password" className="mr-2 font-semibold text-gray-700 mt-2 block">  Password: </label>
            <input
              type="password"
              placeholder="Password"
              className="w-full p-3 mb-4 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <label htmlFor="password" className="mr-2 font-semibold text-gray-700 mt-2 block">  Phone: </label>
            <input
              type="tel"
              placeholder="Phone (e.g., +1234567890)"
              className="w-full p-3 mb-4 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
            <label htmlFor="password" className="mr-2 font-semibold text-gray-700 mt-2 block">  Chat ID: </label>
            <input
              type="text"
              placeholder="Telegram Chat ID"
              className="w-full p-3 mb-6 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={telegramChatId}
              onChange={(e) => setTelegramChatId(e.target.value)}
            />
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
            {message && <div className="bg-blue-100 text-blue-700 p-3 rounded-md mb-4">{message}</div>}
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
                onClick={handleDownloadCSV}
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
            <div className={`p-3 rounded-md mb-4 text-center ${message.includes('failed') ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>
              {message}
            </div>
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
                  checkboxSelection
                  selectionModel={selectedRowId ? [selectedRowId] : []}
                  onSelectionModelChange={(newSelection) => {
                    setSelectedRowId(newSelection[0] || null);
                  }}
                  localeText={{
                    footerRowSelected: (count) =>
                      count === 1
                        ? `Invoice with ID ${selectedRowId} selected`
                        : `${count} invoices selected`,
                  }}
                />





              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h2 className="text-xl font-semibold mb-4 text-gray-700">Category Summary</h2>
              {chartData.labels && chartData.labels.length > 0 ? (
                <div className="flex justify-center h-80">
                  <Pie data={chartData} options={{ maintainAspectRatio: false, responsive: true }} />
                </div>
              ) : (
                <p className="text-center text-gray-600">No category data available.</p>
              )}
            </div>
          </div>


          <TaskPoller
           token={token}
           onUpdate={() => fetchUserInvoices(token, setInvoices, setChartData, setMessage, clearMessage, setToken, setView)}
           />



        </div>
      );
    }


  };

  return <>{renderContent()}</>;
}

export default App;


