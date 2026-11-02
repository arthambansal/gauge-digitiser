# Sources of the real gauge photos

All photos are from Wikimedia Commons, downloaded as 800 px wide thumbnails, unmodified.
Licences require attribution (CC BY / CC BY-SA) — keep this file with the images and credit them in the report.

| File | Original title | Author | Licence | Source |
|---|---|---|---|---|
| real_wika_600bar.jpg | 1990s WIKA analog pressure gauge 0 to 600 bar Alexander Wiegand Germany.jpg | R. Henrik Nilsson | CC BY 4.0 | https://commons.wikimedia.org/wiki/File:1990s_WIKA_analog_pressure_gauge_0_to_600_bar_Alexander_Wiegand_Germany.jpg |
| real_budenberg_lbs.jpg | Budenberg Gauge LBS-PSI.JPG | Dcolvin (talk) (Uploads) | CC0 | https://commons.wikimedia.org/wiki/File:Budenberg_Gauge_LBS-PSI.JPG |
| real_wika_4000psi.jpg | Gauge.jpg | Hey Paul from State College, PA, USA | CC BY 2.0 | https://commons.wikimedia.org/wiki/File:Gauge.jpg |
| real_wika_minicheck_15psi.jpg | Hyperbaric oxygen cell testing pot pressure gauge IMG 20201209 153847.jpg | Pbsouthwood | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Hyperbaric_oxygen_cell_testing_pot_pressure_gauge_IMG_20201209_153847.jpg |
| real_maximator_2500bar.jpg | MAXIMATOR-High-Pressure-Manometer-01a.jpg | CEphoto, Uwe Aranas | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:MAXIMATOR-High-Pressure-Manometer-01a.jpg |
| real_manometer_15kp.jpg | Manometer 104026.jpg | Nord68 | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Manometer_104026.jpg |
| real_astralpool_3bar.jpg | Manómetro 3 psi 1.jpg | Amfeli | CC BY 4.0 | https://commons.wikimedia.org/wiki/File:Man%C3%B3metro_3_psi_1.jpg |
| real_tyre_gauge_4p5bar.jpg | Porsche Tire Pressure Gauge (9207945919).jpg | Antti | CC BY 2.0 | https://commons.wikimedia.org/wiki/File:Porsche_Tire_Pressure_Gauge_(9207945919).jpg |
| real_sprinkler_300psi.jpg | Pressure Gauge at UCSD.jpg | Ncysea | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Pressure_Gauge_at_UCSD.jpg |
| real_wall_gauge_60.jpg | Pressure Gauge.jpg | In Transit | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Pressure_Gauge.jpg |
| real_usg_4000psi.jpg | Psidial.jpg | leapingllamas | CC BY 2.0 | https://commons.wikimedia.org/wiki/File:Psidial.jpg |
| real_vdo_oil_10bar.jpg | VDO engine oil pressure gauge.jpg | R. Henrik Nilsson | CC BY 4.0 | https://commons.wikimedia.org/wiki/File:VDO_engine_oil_pressure_gauge.jpg |

## How the labels in labels.csv were made

Labelled by eye (by Claude, the coding assistant) from the photos at 2x zoom with a 5° angle grid:
- **true_value**: needle position read against the printed scale; cross-checked against the second scale where the gauge has two (psi/kPa, bar/psi).
- **min_angle / sweep**: a straight line fitted through the angles of several major ticks, measured from the needle pivot.
- **label_uncertainty**: my estimate of the reading error of the label itself, in gauge units and in % of full scale.
Errors smaller than the label uncertainty are not meaningful. Seven of the twelve gauges are at rest (zero),
because product photos are usually taken unpressurised.
