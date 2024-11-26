import React, { useEffect, useState } from 'react';
import { getCircuitStats } from '../api';


const CircuitrStats = () => {
  const [circuits, setCircuits] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await getCircuitStats();
        setCircuits(data);
      } catch (error) {
        console.error('Error fetching data:', error);
      }
    };

    fetchData();
  }, []);

  return (
    <div>
      <h1>Formula 1 Circuits Stats</h1>
      <ul>
        {circuits.map((circuits) => (
          <li key={circuits.circuit_name}>
            {circuits.circuit_id}: {circuits.country} cty, {circuits.locality} location
          </li>
        ))}
      </ul>
    </div>
  );
};

export default CircuitrStats;