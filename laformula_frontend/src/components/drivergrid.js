import React, { useState, useEffect } from 'react';
import './DriverGrid.css';
import axios from 'axios';
import './style.css';
import LoadingCar from '../components/loading_car'

const API_BASE_URL = 'http://127.0.0.1:8000'; // Replace with your Django API base URL
//temp
const username = "admin";
const password = "djangoadmin";
const credentials = btoa(`${username}:${password}`);



const getImagePath = (driver_id) => {
    try {
        // Dynamically import the image using the driver_id
        return require(`../assets/images/driver_grid/${driver_id}_drivergrid.jpg`);
    } catch (err) {
        // Fallback to a default image if not found
        return require(`../assets/images/driver_grid/default_drivergrid.png`);
    }
};

const DriverGrid = () => {
    const [drivers, setDrivers] = useState([]);
    const [season, setSeason] = useState(2024); // Default year
    const [round, setRound] = useState(1); // Default round
    const [isLoading, setIsLoading] = useState(false);
    const [raceName, setRaceName] = useState(''); // For storing race name

    useEffect(() => {
        const fetchDrivers = async () => {
            setIsLoading(true);
            try {
                const response = await axios.get(`${API_BASE_URL}/driver-season-rounds?season=${season}&round=${round}`,{            
                    headers: {
                    Authorization: `Basic ${credentials}`,
                  },});
                console.log('API Response:', response.data);
                const data = await response.data;
                
                const driversData = data.map(item => item.driver);
                setDrivers(driversData);
            } catch (error) {
                console.error('Error loading drivers:', error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchDrivers();
    }, [season, round]); // Re-fetch data when season or round changes


    useEffect(() => {
        const fetchRaceName = async () => {
            try {
                const response = await axios.get(`${API_BASE_URL}/race-season-rounds/?season=${season}&round=${round}`);
                if (response.data && response.data.length > 0) {
                    setRaceName(response.data[0].race_name); // Assuming race_name is in the response
                } else {
                    setRaceName('Race not found');
                }
            } catch (error) {
                console.error('Error loading race name:', error);
                setRaceName('Error fetching race');
            }
        };

        fetchRaceName();
    }, [season, round]); // Re-fetch race name when season or round changes

    
    return (
        <div>
            <h2 className="race-title">{raceName}</h2>
            <div className="filters">
                <label className="filter-label">
                    Season:
                    <select value={season} onChange={(e) => setSeason(Number(e.target.value))}>
                        <option value="2024">2024</option>
                        <option value="2023">2023</option>
                        <option value="2022">2022</option>
                        <option value="2021">2021</option>
                        <option value="2020">2020</option>
                        <option value="2019">2019</option>
                    </select>
                </label>
                
                <label className="filter-label">
                    Round:
                    <select value={round} onChange={(e) => setRound(Number(e.target.value))}>
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="4">4</option>
                        <option value="5">5</option>
                        <option value="6">6</option>
                        <option value="7">7</option>
                        <option value="8">8</option>
                        <option value="9">9</option>
                        <option value="10">10</option>
                        <option value="11">11</option>
                        <option value="12">12</option>
                        <option value="13">13</option>
                        <option value="14">14</option>
                        <option value="15">15</option>
                        <option value="16">16</option>
                        <option value="17">17</option>
                        <option value="18">18</option>
                        <option value="19">19</option>
                        <option value="20">20</option>
                        <option value="21">21</option>
                        <option value="22">22</option>
                        <option value="23">23</option>
                        <option value="24">24</option>

                    </select>
                </label>
            </div>

            {isLoading ? (
                <LoadingCar />
            ) : (
                <div className="driver-grid">
                    {drivers.length === 0 ? (
                        <div>No drivers found for the selected season and round.</div>
                    ) : (
                        drivers.map((drivers, index) => (
                            <div className="driver-card" key={index}>
                                <div className="driver-image">
                                    <img src={getImagePath(drivers.driver_id)}  alt={drivers.family_name} />
                                </div>
                                <div className="driver-info">
                                    <h3>{drivers.family_name}</h3>
                                    <p>Drive ID: {drivers.driver_id}</p>
                                    <p>Given Name: {drivers.given_name}</p>
                                    <p>Family Name: {drivers.family_name}</p>
                                    <p>Age: {new Date().getFullYear() - new Date(drivers.date_of_birth).getFullYear()}</p>
                                    <p>Nationality: {drivers.nationality}</p>
                                    <p>
                                        <a href={drivers.url} target="_blank" rel="noopener noreferrer">Wikipedia</a>
                                    </p>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
};

export default DriverGrid;