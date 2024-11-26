import React, { useState, useEffect } from 'react';
import "./HomepageSlider.css"; // Include your CSS for slider

const Slider = () => {
  const [activeSlide, setActiveSlide] = useState(1);

  const handleSlideChange = (slideNumber) => {
    setActiveSlide(slideNumber);
  };
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveSlide(prevSlide => (prevSlide === 4 ? 1 : prevSlide + 1));
    }, 15000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="slider-container">
        <div className="css-slider-wrapper">
        {/* Radio buttons */}
        <input
            type="radio"
            name="slider"
            className="slide-radio1"
            id="slider_1"
            checked={activeSlide === 1}
            onChange={() => handleSlideChange(1)}
        />
        <input
            type="radio"
            name="slider"
            className="slide-radio2"
            id="slider_2"
            checked={activeSlide === 2}
            onChange={() => handleSlideChange(2)}
        />
        <input
            type="radio"
            name="slider"
            className="slide-radio3"
            id="slider_3"
            checked={activeSlide === 3}
            onChange={() => handleSlideChange(3)}
        />
        <input
            type="radio"
            name="slider"
            className="slide-radio4"
            id="slider_4"
            checked={activeSlide === 4}
            onChange={() => handleSlideChange(4)}
        />

        {/* Slider Pagination */}
        <div className="slider-pagination">
            <label htmlFor="slider_1" className="page1"></label>
            <label htmlFor="slider_2" className="page2"></label>
            <label htmlFor="slider_3" className="page3"></label>
            <label htmlFor="slider_4" className="page4"></label>
        </div>

        {/* Sliders */}
        {activeSlide === 1 && (
            <div className="slider slide-1">
            <div className="slider-content">
                <h2>Welcome to Laformula</h2>
                <h4>This Website is under construction</h4>
                <button type="button" className="detail-button">More Detail</button>
            </div>
            <div className="number-pagination">
                <span>1</span>
            </div>
            <div className="reference-link-text">
                    <a href="https://www.reddit.com/r/F1Porn/comments/1f9je07/lewis_hamilton_mercedes_f1_w08_eq_power_1st_free/">Reference: https://www.reddit.com/r/F1Porn/comments/1f9je07/lewis_hamilton_mercedes_f1_w08_eq_power_1st_free/</a>
            </div>
            </div>
        )}
        {activeSlide === 2 && (
            <div className="slider slide-2">
            <div className="slider-content">
                <h2>Welcome to Laformula</h2>
                <h4>Drivers Tab is Demo-ready</h4>
                <button type="button" className="detail-button">More Detail</button>
            </div>
            <div className="number-pagination">
                <span>2</span>
            </div>
                <div className="reference-link-text">
                    <a href="https://www.reddit.com/r/F1Porn/comments/1d2lfot/oscar_piastri_mclaren_mcl38_3rd_free_practice/">Reference: https://www.reddit.com/r/F1Porn/comments/1d2lfot/oscar_piastri_mclaren_mcl38_3rd_free_practice/</a>
                </div>
            </div>
        )}
        {activeSlide === 3 && (
            <div className="slider slide-3">
            <div className="slider-content">
                <h2>Welcome to Laformula</h2>
                <h4>Description needed</h4>
                <button type="button" className="detail-button">More Detail</button>
            </div>
            <div className="number-pagination">
                <span>3</span>
            </div>
                <div className="reference-link-text">
                    <a href="https://www.reddit.com/r/F1Porn/comments/1czpwz8/charles_leclerc_ferrari_sf24_2nd_free_practice/">Reference: https://www.reddit.com/r/F1Porn/comments/1czpwz8/charles_leclerc_ferrari_sf24_2nd_free_practice/</a>
                </div>
            </div>
        )}
        {activeSlide === 4 && (
            <div className="slider slide-4">  
            <div className="slider-content">
                <h2>Welcome to Laformula</h2>
                <h4>Some analysis will be appreciated</h4>
                <button type="button" className="detail-button">More Detail</button>
            </div>
            <div className="number-pagination">
                <span>4</span>
            </div>
                <div className="reference-link-text">
                    <a href="https://www.reddit.com/r/F1Porn/comments/12e31ax/felipe_massa_ferrari_f2008_perform_a_pitstop_race/">Reference: https://www.reddit.com/r/F1Porn/comments/12e31ax/felipe_massa_ferrari_f2008_perform_a_pitstop_race/</a>
                </div>
            </div>
        )}
        </div>
    </div>
  );
};

export default Slider;