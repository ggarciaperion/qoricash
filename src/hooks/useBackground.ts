import { useAuth } from '../contexts/AuthContext';

// Fondo para persona natural (DNI / CE)
const BG_NATURAL = require('../../assets/dcv.png');
// Fondo para empresa / persona jurídica (RUC — 11 dígitos)
const BG_EMPRESA = require('../../assets/lo_empresa.jpg');

/**
 * Devuelve la imagen de fondo correcta según el tipo de cliente autenticado.
 * - document_type === 'RUC'  → empresa  → lo_empresa.jpg  (jh.png)
 * - DNI / CE / sin sesión    → natural  → lo.jpg          (yu.png)
 */
export const useBackground = () => {
  const { client } = useAuth();
  const isEmpresa = client?.document_type === 'RUC';
  return isEmpresa ? BG_EMPRESA : BG_NATURAL;
};
