import React, { useState } from 'react';
import { Link } from 'react-router-dom';  // Import Link from react-router-dom
import './Navbar.css';
import cartoonf1sideview1 from '../assets/images/cartoonf1sideview1.png';

const Navbar = () => {
    const [isOpen, setIsOpen] = useState(false);

    const toggleMenu = () => {
        setIsOpen(!isOpen);
    };

    return (
        <nav className="navbar">
            <div className="navbar-logo">
                <Link to="/">LaFormula</Link>  {/* Home link */}
            </div>
            <div className="navbar-image">
                <img src={cartoonf1sideview1} alt="bannerlogo" />
            </div>
            <div className="navbar-image">
                <img src={cartoonf1sideview1} alt="bannerlogo" />
            </div>
            <div className="navbar-image">
                <img src={cartoonf1sideview1} alt="bannerlogo" />
            </div>
            <div className="navbar-image">
                <img src={cartoonf1sideview1} alt="bannerlogo" />
            </div>
            <div className="navbar-image">
                <img src={cartoonf1sideview1} alt="bannerlogo" />
            </div>
            <ul className={`navbar-links ${isOpen ? 'active' : ''}`}>
                <li><Link to="/home">Home</Link></li>
                <li><Link to="/drivers">Drivers</Link></li>
                <li><Link to="/teams">Teams</Link></li>
                <li><Link to="/races">Races</Link></li>
                <li><Link to="/about">About</Link></li>
            </ul>
            <div className="navbar-toggle" onClick={toggleMenu}>
                <span></span>
                <span></span>
                <span></span>
            </div>
        </nav>
    );
};

export default Navbar;