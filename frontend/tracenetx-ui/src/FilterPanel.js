import React, { useState } from 'react';

function FilterPanel({ onFilter }) {
  const [ip, setIp] = useState('');
  const [phone, setPhone] = useState('');
  const [city, setCity] = useState('');

  const apply = () => onFilter({ ip, phone, city });
  const reset = () => {
    setIp(''); setPhone(''); setCity('');
    onFilter({ ip: '', phone: '', city: '' });
  };

  return (
    <div className="filter-panel">
      <h3>🔍 Filters</h3>
      <input
        placeholder="IP Address (e.g. 192.168.1.1)"
        value={ip}
        onChange={e => setIp(e.target.value)}
      />
      <input
        placeholder="Phone Number"
        value={phone}
        onChange={e => setPhone(e.target.value)}
      />
      <input
        placeholder="City (e.g. Delhi)"
        value={city}
        onChange={e => setCity(e.target.value)}
      />
      <button className="btn-apply" onClick={apply}>Apply Filter</button>
      <button className="btn-reset" onClick={reset}>Reset</button>
    </div>
  );
}

export default FilterPanel;
