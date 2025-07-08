import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './global.css';

import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);


