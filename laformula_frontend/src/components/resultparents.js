import React, { useState } from 'react';
import DriverChild from './resultchild';
import './ResultParents.css';

const RaceParent = ({season, round, raceName, driver_results}) => {
    const [isOpen, setIsOpen] = useState(false);

    const toggleOpen = () => {
        setIsOpen(!isOpen);
    };

    return (
        <div className="race-parent">
            <div className="race-bar" onClick={toggleOpen}>
                <h3> {season}  Round#{round}  {raceName}</h3>
                <span>{isOpen ? '▲' : '▼'}</span>
            </div>

            {isOpen && (
                <div className="driver-list">
                    {driver_results.map((driver_result, index) => (
                        <DriverChild  key = {index} constructor={driver_result.constructor.constructor_name} drivers_lastname={driver_result.driver.given_name} drivers_firstname={driver_result.driver.family_name} 
                        number = {driver_result.number} finished_position={driver_result.finished_position} grid={driver_result.grid} status={driver_result.status} avg_spd={driver_result.avg_spd} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default RaceParent;