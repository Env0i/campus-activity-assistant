window.__esmOrder.push('l02');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['02'] = { id: 2, name: 'state-02' };
  window.__legacyLayers.view['02'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['02'].id; }
  };
  window.__legacyLayers.controller['02'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['02'].id,
        card: window.__legacyLayers.view['02'].render(),
        label: 'controller-02'
      };
    }
  };
})();
