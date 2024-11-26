import React from 'react';
import './ResultChild.css';

const DriverChild = ({constructor, drivers_lastname, drivers_firstname, number, finished_position, grid, status, avg_spd}) => {
    return (
        <div className="driver-child">
            <span>{finished_position}</span>
            <span>{drivers_lastname} {drivers_firstname}</span>
            <span>{constructor}</span>
            <span>{number} {grid} {status} {avg_spd}</span>
        </div>
    );
};

export default DriverChild;