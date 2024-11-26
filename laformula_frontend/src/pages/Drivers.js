import React from 'react';
import DriverGrid from '../components/drivergrid'; // Adjust the path as necessary
import './drivers.css';
const Drivers = () => {
    return (
        <div>
            <h1 className="title">Formula 1 Drivers For</h1>
            <DriverGrid />
        </div>
    );
};

export default Drivers;