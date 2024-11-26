import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000'; // Replace with your Django API base URL
//temp
const username = "admin";
const password = "djangoadmin";
const credentials = btoa(`${username}:${password}`);

export const getCircuitStats = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/circuits/`,{
        headers: {
          Authorization: `Basic ${credentials}`,
        },
      });
    return response.data;
  } catch (error) {
    console.error('Error fetching circuits stats:', error);
    throw error;
  }
};