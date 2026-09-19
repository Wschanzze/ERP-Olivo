import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, Legend 
} from 'recharts';
import { 
  DollarSign, Sprout, Users, Package, 
  TrendingUp, Truck, AlertCircle, RefreshCw, Layers 
} from 'lucide-react';

const COLORS = ['#3D4A2A', '#6B894B', '#C29B38', '#8B263E', '#4E5F36', '#B6C7A2'];

export default function App({ apiUrl }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(apiUrl);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const json = await response.json();
      setData(json);
    } catch (err) {
      console.error('Error cargando KPIs:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [apiUrl]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 bg-white rounded-2xl border border-slate-200">
        <RefreshCw className="w-8 h-8 text-[#3D4A2A] animate-spin mb-3" />
        <p className="text-sm font-medium text-slate-600">Calculando métricas agregadas del ERP...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl flex items-center justify-between text-rose-900">
        <div className="flex items-center space-x-3">
          <AlertCircle className="w-6 h-6 text-rose-600 flex-shrink-0" />
          <div>
            <p className="font-bold text-sm">No se pudo cargar el tablero analítico</p>
            <p className="text-xs text-rose-700">{error}</p>
          </div>
        </div>
        <button 
          onClick={fetchData}
          className="px-3 py-1.5 bg-white border border-rose-300 rounded-lg text-xs font-semibold hover:bg-rose-100"
        >
          Reintentar
        </button>
      </div>
    );
  }

  const { resumen, variedades, costos_por_categoria, ultimas_cosechas } = data;

  const dataVariedades = variedades.map(v => ({
    name: v.variedad_olivo,
    superficie: parseFloat(v.superficie || 0),
    cuadros: v.cantidad_cuadros,
  }));

  const dataCostos = costos_por_categoria.map(c => ({
    name: c.tipo_origen,
    value: parseFloat(c.total_ars || 0),
  }));

  const dataCosechas = ultimas_cosechas.map(c => ({
    lote: c.cuadro__codigo,
    kg: parseFloat(c.kg_cosechados || 0),
    rinde: parseFloat(c.rendimiento_graso_porcentaje || 0),
  }));

  return (
    <div className="space-y-6">
      
      {/* Barra de Estado del Tablero */}
      <div className="flex justify-between items-center bg-white px-5 py-3 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center space-x-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Isla React Activa • Motor DRF en Línea
          </span>
        </div>
        <button 
          onClick={fetchData} 
          className="flex items-center space-x-1.5 text-xs text-slate-500 hover:text-[#3D4A2A] font-semibold transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Actualizar Datos</span>
        </button>
      </div>

      {/* FILA 1: Cards Métricas Principales (4 por fila conforme a especificación) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        
        {/* Card 1: Dinero en Caja y Bancos */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:border-[#8FA872] transition-all min-w-0">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Tesorería (ARS)</span>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-700 flex-shrink-0">
              <DollarSign className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <p className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight font-mono truncate">
              ${resumen.total_caja_bancos_ars.toLocaleString('es-AR', { maximumFractionDigits: 0 })}
            </p>
            <p className="text-xs text-emerald-700 font-medium mt-1 truncate" title={`+ u$s ${resumen.total_caja_bancos_usd.toLocaleString('en-US', { maximumFractionDigits: 0 })} en Santander`}>
              + u$s {resumen.total_caja_bancos_usd.toLocaleString('en-US', { maximumFractionDigits: 0 })} en Santander
            </p>
          </div>
        </div>

        {/* Card 2: Deudores por Ventas vs Proveedores */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:border-[#8FA872] transition-all min-w-0">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Cuentas x Cobrar</span>
            <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center text-blue-700 flex-shrink-0">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <p className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight font-mono truncate">
              ${resumen.nos_deben_clientes_ars.toLocaleString('es-AR', { maximumFractionDigits: 0 })}
            </p>
            <p className="text-xs text-rose-600 font-medium mt-1 truncate" title={`Debemos a proveedores: $${resumen.debemos_proveedores_ars.toLocaleString('es-AR', { maximumFractionDigits: 0 })}`}>
              Debemos a proveedores: ${resumen.debemos_proveedores_ars.toLocaleString('es-AR', { maximumFractionDigits: 0 })}
            </p>
          </div>
        </div>

        {/* Card 3: Cosecha Total Campaña */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:border-[#8FA872] transition-all min-w-0">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Cosecha Acumulada</span>
            <div className="w-9 h-9 rounded-xl bg-[#EAEFE3] flex items-center justify-center text-[#3D4A2A] flex-shrink-0">
              <Sprout className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <p className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight font-mono truncate">
              {resumen.total_cosecha_kg.toLocaleString('es-AR', { maximumFractionDigits: 0 })} <span className="text-sm font-sans font-bold text-slate-500">kg</span>
            </p>
            <p className="text-xs text-[#6B894B] font-medium mt-1 truncate">
              {resumen.total_cuadros} cuadros en recolección
            </p>
          </div>
        </div>

        {/* Card 4: Superficie Neta Cultivada */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:border-[#8FA872] transition-all min-w-0">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Superficie Activa</span>
            <div className="w-9 h-9 rounded-xl bg-amber-50 flex items-center justify-center text-amber-700 flex-shrink-0">
              <Layers className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <p className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight font-mono truncate">
              {resumen.total_hectareas} <span className="text-sm font-sans font-bold text-slate-500">ha</span>
            </p>
            <p className="text-xs text-amber-700 font-medium mt-1 truncate">
              100% bajo riego presurizado
            </p>
          </div>
        </div>

      </div>

      {/* FILA 2: Cards Métricas Secundarias (4 por fila) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 sm:gap-5">
        
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center space-x-3 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center flex-shrink-0">
            <Users className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase block truncate">Personal en Campo Hoy</span>
            <p className="text-base sm:text-lg font-bold text-slate-900 truncate">{resumen.presentes_hoy} de {resumen.personal_activo} registrados</p>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center space-x-3 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-oliva-50 text-[#3D4A2A] flex items-center justify-center flex-shrink-0">
            <Package className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase block truncate">Stock Insumos Valorizado</span>
            <p className="text-base sm:text-lg font-bold text-slate-900 font-mono truncate">${resumen.valor_stock_ars.toLocaleString('es-AR', { maximumFractionDigits: 0 })}</p>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center space-x-3 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center flex-shrink-0">
            <Truck className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase block truncate">Tractores y Máquinas</span>
            <p className="text-base sm:text-lg font-bold text-slate-900 truncate">{resumen.maquinaria_operativa} Operativas ({resumen.maquinaria_taller} Taller)</p>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center space-x-3 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-700 flex items-center justify-center flex-shrink-0">
            <TrendingUp className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase block truncate">Resultado Neto Estimado</span>
            <p className="text-base sm:text-lg font-bold text-emerald-700 font-mono truncate">${resumen.resultado_neto_estimado.toLocaleString('es-AR', { maximumFractionDigits: 0 })}</p>
          </div>
        </div>

      </div>

      {/* GRÁFICOS RECHARTS */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Gráfico 1: Superficie por Variedad de Olivo */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-1">
            Superficie por Variedad de Olivo (Hectáreas)
          </h3>
          <p className="text-xs text-slate-400 mb-6">Distribución agronómica según aptitud: mesa vs almazara.</p>
          
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dataVariedades} margin={{ top: 10, right: 15, left: -10, bottom: 20 }}>
                <XAxis dataKey="name" stroke="#888888" fontSize={11} tickLine={false} />
                <YAxis stroke="#888888" fontSize={11} tickLine={false} unit=" ha" />
                <Tooltip 
                  formatter={(val) => [`${val} ha`, 'Superficie']} 
                  contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8DE' }}
                />
                <Bar dataKey="superficie" fill="#3D4A2A" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Gráfico 2: Cosecha Reciente y Rinde Graso */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-1">
            Lotes de Cosecha (Kg recolectados)
          </h3>
          <p className="text-xs text-slate-400 mb-6">Rendimiento por cuadro ingresado en almazara y planta de mesa.</p>
          
          <div className="h-64">
            {dataCosechas.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dataCosechas} margin={{ top: 10, right: 15, left: -10, bottom: 20 }}>
                  <XAxis dataKey="lote" stroke="#888888" fontSize={11} tickLine={false} />
                  <YAxis stroke="#888888" fontSize={11} tickLine={false} />
                  <Tooltip 
                    formatter={(val) => [`${val.toLocaleString()} kg`, 'Cosechado']}
                    contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8DE' }}
                  />
                  <Bar dataKey="kg" fill="#C29B38" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-xs text-slate-400">
                No hay lotes de cosecha registrados
              </div>
            )}
          </div>
        </div>

      </div>

    </div>
  );
}
