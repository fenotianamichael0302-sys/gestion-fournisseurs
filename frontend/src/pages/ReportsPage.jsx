import { useEffect, useState } from 'react'
import { api, downloadFile, getErrorMessage } from '../api/client'
import Button from '../components/Button'
import DataTable from '../components/DataTable'
import { FormField, SelectField } from '../components/FormField'
import PageHeader from '../components/PageHeader'
import { useToast } from '../context/useToast'
import useApiList from '../hooks/useApiList'

function currentYear() {
  return String(new Date().getFullYear())
}

function money(value) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .format(Number(value || 0))
}

function ExportButtons({ report, exporting, onExport }) {
  return (
    <div className="report-export-actions">
      {['pdf', 'xlsx'].map((format) => {
        const key = `${report}-${format}`
        return (
          <Button
            key={format}
            variant="secondary"
            size="small"
            loading={exporting === key}
            disabled={Boolean(exporting) && exporting !== key}
            onClick={() => onExport(report, format)}
          >
            {format.toUpperCase()}
          </Button>
        )
      })}
    </div>
  )
}

export default function ReportsPage() {
  const toast = useToast()
  const suppliers = useApiList('suppliers')
  const [filters, setFilters] = useState({ supplier: '', date_from: '', date_to: '', year: currentYear(), product: '' })
  const [appliedFilters, setAppliedFilters] = useState(filters)
  const [invoicePage, setInvoicePage] = useState(1)
  const [pricePage, setPricePage] = useState(1)
  const [reports, setReports] = useState({ spending: [], monthly: [], invoices: [], invoiceCount: 0, comparisons: [], comparisonCount: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [exporting, setExporting] = useState('')

  function changeFilter(event) {
    setFilters((current) => ({ ...current, [event.target.name]: event.target.value }))
  }

  function applyFilters(event) {
    event.preventDefault()
    setInvoicePage(1)
    setPricePage(1)
    setAppliedFilters(filters)
  }

  async function exportReport(report, format) {
    const params = new URLSearchParams({ export: format })
    for (const key of ['supplier', 'date_from', 'date_to']) {
      if (appliedFilters[key]) params.set(key, appliedFilters[key])
    }
    if (report === 'monthly-purchases') params.set('year', appliedFilters.year)
    if (report === 'price-comparison' && appliedFilters.product) params.set('product', appliedFilters.product)
    const key = `${report}-${format}`
    setExporting(key)
    try {
      const filename = await downloadFile(
        `/reports/${report}/?${params.toString()}`,
        `${report}.${format}`,
      )
      toast.success(`Export téléchargé : ${filename}`)
    } catch (exportError) {
      toast.error(getErrorMessage(exportError))
    } finally {
      setExporting('')
    }
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    const common = {
      ...(appliedFilters.supplier ? { supplier: appliedFilters.supplier } : {}),
      ...(appliedFilters.date_from ? { date_from: appliedFilters.date_from } : {}),
      ...(appliedFilters.date_to ? { date_to: appliedFilters.date_to } : {}),
    }
    Promise.all([
      api.get('/reports/spending-by-supplier/', { params: common }),
      api.get('/reports/monthly-purchases/', { params: { ...common, year: appliedFilters.year } }),
      api.get('/reports/unpaid-invoices/', { params: { ...common, page: invoicePage } }),
      api.get('/reports/price-comparison/', { params: { ...common, ...(appliedFilters.product ? { product: appliedFilters.product } : {}), page: pricePage } }),
    ])
      .then(([spendingResponse, monthlyResponse, invoiceResponse, priceResponse]) => {
        if (!active) return
        setReports({
          spending: spendingResponse.data,
          monthly: monthlyResponse.data,
          invoices: invoiceResponse.data.results,
          invoiceCount: invoiceResponse.data.count,
          comparisons: priceResponse.data.results,
          comparisonCount: priceResponse.data.count,
        })
      })
      .catch((requestError) => { if (active) setError(getErrorMessage(requestError)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [appliedFilters, invoicePage, pricePage])

  const spendingColumns = [
    { key: 'supplier', header: 'Fournisseur', sortable: true },
    { key: 'total_ht', header: 'Total HT', sortable: true, render: (value) => money(value) },
    { key: 'total_tax', header: 'Taxes', sortable: true, render: (value) => money(value) },
    { key: 'total_ttc', header: 'Total TTC', sortable: true, render: (value) => money(value) },
  ]
  const monthlyColumns = [
    { key: 'month', header: 'Mois', sortable: true },
    { key: 'total_ht', header: 'Total HT', sortable: true, render: (value) => money(value) },
    { key: 'total_tax', header: 'Taxes', sortable: true, render: (value) => money(value) },
    { key: 'total_ttc', header: 'Total TTC', sortable: true, render: (value) => money(value) },
  ]
  const invoiceColumns = [
    { key: 'invoice_number', header: 'Facture' },
    { key: 'supplier', header: 'Fournisseur' },
    { key: 'due_date', header: 'Échéance' },
    { key: 'total_ttc', header: 'Total TTC', render: (value) => money(value) },
    { key: 'balance_due', header: 'Reste dû', render: (value) => money(value) },
  ]
  const comparisonColumns = [
    { key: 'product_name', header: 'Produit' },
    { key: 'supplier', header: 'Fournisseur' },
    { key: 'average_price', header: 'Prix unitaire moyen', render: (value) => money(value) },
  ]

  return (
    <section>
      <PageHeader
        title="Rapports et statistiques"
        description="Analysez les dépenses, les échéances et les prix d’achat."
      />
      <form className="report-filters panel-card" onSubmit={applyFilters}>
        <SelectField
          label="Fournisseur"
          name="supplier"
          value={filters.supplier}
          onChange={changeFilter}
          options={[
            { value: '', label: 'Tous les fournisseurs' },
            ...suppliers.rows.map((supplier) => ({ value: String(supplier.id), label: supplier.company_name })),
          ]}
        />
        <FormField label="Date début" name="date_from" type="date" value={filters.date_from} onChange={changeFilter} />
        <FormField label="Date fin" name="date_to" type="date" value={filters.date_to} onChange={changeFilter} />
        <FormField label="Année" name="year" type="number" min="2000" max="9999" value={filters.year} onChange={changeFilter} required />
        <FormField label="Produit à comparer" name="product" value={filters.product} onChange={changeFilter} />
        <button className="button button-primary" type="submit">Appliquer les filtres</button>
      </form>
      {error && <p className="inline-alert" role="alert">{error}</p>}
      <div className="report-sections">
        <article className="panel-card">
          <div className="panel-heading"><h2>Dépenses par fournisseur</h2><ExportButtons report="spending-by-supplier" exporting={exporting} onExport={exportReport} /></div>
          <DataTable columns={spendingColumns} rows={reports.spending} loading={loading} emptyMessage="Aucune dépense pour cette période." />
        </article>
        <article className="panel-card">
          <div className="panel-heading"><h2>Achats par mois · {appliedFilters.year}</h2><ExportButtons report="monthly-purchases" exporting={exporting} onExport={exportReport} /></div>
          <DataTable columns={monthlyColumns} rows={reports.monthly} loading={loading} emptyMessage="Aucun achat pour cette année." />
        </article>
        <article className="panel-card">
          <div className="panel-heading"><h2>Factures impayées</h2><ExportButtons report="unpaid-invoices" exporting={exporting} onExport={exportReport} /></div>
          <DataTable
            columns={invoiceColumns}
            rows={reports.invoices}
            loading={loading}
            page={invoicePage}
            pageSize={25}
            totalItems={reports.invoiceCount}
            onPageChange={setInvoicePage}
            emptyMessage="Aucune dette en cours."
          />
        </article>
        <article className="panel-card">
          <div className="panel-heading"><h2>Comparaison des prix</h2><ExportButtons report="price-comparison" exporting={exporting} onExport={exportReport} /></div>
          <DataTable
            columns={comparisonColumns}
            rows={reports.comparisons}
            loading={loading}
            page={pricePage}
            pageSize={25}
            totalItems={reports.comparisonCount}
            onPageChange={setPricePage}
            emptyMessage="Aucun prix trouvé pour ce produit."
          />
        </article>
      </div>
    </section>
  )
}
