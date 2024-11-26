import LoadingCar from '../components/loading_car'
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import RaceParent from './resultparents';
import './ResultParents.css';



const API_BASE_URL = 'http://127.0.0.1:8000'; // Replace with your Django API base URL
//temp
const username = "admin";
const password = "djangoadmin";
const credentials = btoa(`${username}:${password}`);


const RacePage = () => {
    const [races, setRaces] = useState([]);
    const [raceName, setRaceName] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [season, setSeason] = useState(2024);
    const [round, setRound] = useState(1); 

    useEffect(() => {
        const fetchResults = async () => {
            setIsLoading(true);
            try {
                const response = await axios.get(`${API_BASE_URL}/result-season-rounds?season=${season}&round=${round}`,{            
                    headers: {
                    Authorization: `Basic ${credentials}`,
                  },});
                console.log('API Response:', response.data);
                setRaces(response.data);
    
            } catch (error) {
                console.error('Error loading drivers:', error);
            } finally {
            setIsLoading(false);
            }
        };
        fetchResults();
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
            {isLoading ? (
                <LoadingCar />
            ) : (
            <div className="race-page">
                {/* {races.map((races) => ( */}
                <RaceParent  season={season} round={round} raceName={raceName} driver_results={races} />
                {/* ))} */}
            </div>
            )}
        </div>
    );
};  

export default RacePage;