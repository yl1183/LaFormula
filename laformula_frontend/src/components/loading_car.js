import React from 'react';
import './LoadingCar.css'; // Import your CSS for the car animation
import carImage from '../assets/images/cartoonf1sideview1-removebg.png';
const LoadingCar = () => {
    return (
        <div className="loading-container">
            <div className="car-wrapper">
                <div className="band"></div>
                <img src={carImage} alt="car" className="car" />
                <div className="loading-text">Loading...</div>
            </div>
        </div>
    );
};

export default LoadingCar;


