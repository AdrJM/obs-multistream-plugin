fetch('http://localhost:5000/status')
  .then(response => response.json())
  .then(data => {
      const platform = document.getElementById('platform')
      CSSContainerRule.innerHTML = JSON.stringify(data)
  })