import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, DollarSign, Download, Package, Receipt, TrendingUp, Wallet } from 'lucide-react';
import AdminLayout from '@/components/layout/AdminLayout';
import LoadError from '@/components/ui/LoadError';
import {
  useGetFinanceSummaryQuery,
  useGetLatestTransactionsQuery,
} from '@/store/api/paymentsApi';

function money(value) {
  if (value == null) return '—';
  return `৳${Number(value || 0).toLocaleString()}`;
}

export default function FinanceSummaryPage() {
  const [dateRange, setDateRange] = useState({
    start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
  });

  const { data: summary, isLoading, isError, refetch } = useGetFinanceSummaryQuery();
  const {
    data: transactionsData,
    isLoading: transactionsLoading,
    isError: transactionsError,
    refetch: refetchTransactions,
  } = useGetLatestTransactionsQuery(dateRange);

  const transactions = transactionsData?.transactions || [];

  return (
    <AdminLayout title="Finance Summary">
      <div className="flex flex-col gap-4 mb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Link href="/finance" className="inline-flex items-center gap-1 text-sm text-primary-600 mb-2">
            <ArrowLeft className="w-4 h-4" />
            Back to Finance
          </Link>
          <h1 className="text-2xl font-semibold text-gray-900">Financial Summary</h1>
          <p className="text-sm text-gray-500">
            Overall position from completed sales, recorded costs, and manual income. Review the latest income and expense transactions below.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="date"
            value={dateRange.start_date}
            onChange={(event) => setDateRange({ ...dateRange, start_date: event.target.value })}
            className="input w-auto"
            aria-label="From date"
          />
          <span className="text-sm text-gray-400">to</span>
          <input
            type="date"
            value={dateRange.end_date}
            onChange={(event) => setDateRange({ ...dateRange, end_date: event.target.value })}
            className="input w-auto"
            aria-label="To date"
          />
        </div>
      </div>

      {isError ? (
        <LoadError title="Could not load the finance summary" onRetry={refetch} />
      ) : (
        <div className="space-y-6">
          <section>
            <div className="mb-3">
              <h2 className="text-lg font-semibold text-gray-900">Actual results</h2>
              <p className="text-sm text-gray-500">
                Completed sales, purchase costs, manual income, and other recorded expenses.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <Summary icon={DollarSign} label="Order revenue" value={isLoading ? '…' : money(summary?.actual?.current_revenue)} tone="green" hint="Merchandise on completed sales" />
              <Summary icon={DollarSign} label="Share amount" value={isLoading ? '…' : money(summary?.actual?.manual_income_total)} tone="green" hint="Shareholder contributions recorded in Finance" />
              <Summary icon={Wallet} label="Total income" value={isLoading ? '…' : money(summary?.actual?.total_income)} tone="blue" hint="Order revenue plus manual income" />
              <Summary icon={Package} label="Cost of goods sold" value={isLoading ? '…' : money(summary?.actual?.cost_of_goods_sold)} tone="red" hint="Cost of units already sold" />
              <Summary icon={Wallet} label="Realized gross profit" value={isLoading ? '…' : money(summary?.actual?.realized_gross_profit)} tone="blue" hint="Order revenue minus cost of goods sold" />
              <Summary icon={Receipt} label="Total product purchase cost" value={isLoading ? '…' : money(summary?.actual?.total_product_purchase_cost)} tone="purple" hint="Purchase vouchers, product buying, and opening stock" />
              <Summary icon={Receipt} label="Additional expenses" value={isLoading ? '…' : money(summary?.actual?.additional_expenses)} tone="red" hint="Packaging, transportation, and other costs" />
              <Summary icon={Download} label="Inventory losses" value={isLoading ? '…' : money(summary?.actual?.inventory_losses)} tone="purple" hint="Damage, loss, and other non-sale reductions" />
              <Summary icon={DollarSign} label="Delivery collected" value={isLoading ? '…' : money(summary?.actual?.delivery_collected)} tone="green" hint="On completed sales, separate from product revenue" />
              <Summary icon={Download} label="Order discounts" value={isLoading ? '…' : money(summary?.actual?.order_discounts)} tone="purple" hint="On completed sales, separate from product revenue" />
            </div>
            {!isLoading && Number(summary?.actual?.opening_stock_cost) > 0 && (
              <p className="text-xs text-gray-500 mt-2">
                Opening stock cost {money(summary.actual.opening_stock_cost)} is included in total product purchase cost. {summary.actual.opening_stock_note} Purchase vouchers are {money(summary.actual.purchase_vouchers_total)}.
              </p>
            )}
          </section>

          <section>
            <div className="mb-3">
              <h2 className="text-lg font-semibold text-gray-900">Estimates</h2>
              <p className="text-sm text-gray-500">{summary?.estimated?.note || 'Unsold stock is not realized revenue or profit.'}</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              <Summary icon={TrendingUp} label="Estimated selling value" value={isLoading ? '…' : money(summary?.estimated?.selling_value)} tone="green" hint="Remaining stock at current selling prices" />
              <Summary icon={Wallet} label="Estimated remaining profit" value={isLoading ? '…' : money(summary?.estimated?.remaining_gross_profit)} tone="blue" hint="Estimated selling value minus cost still in stock" />
              <Summary icon={Wallet} label="Estimated total profit" value={isLoading ? '…' : money(summary?.estimated?.total_profit)} tone="purple" hint="Realized profit plus remaining profit and manual income, minus additional expenses and losses" />
            </div>
          </section>

          {!isLoading && Number(summary?.awaiting_payment?.quantity) > 0 && (
            <section className="card p-4">
              <h2 className="font-semibold text-gray-900">Awaiting payment</h2>
              <p className="text-sm text-gray-500 mt-1">{summary.awaiting_payment.note}</p>
              <p className="text-sm text-gray-700 mt-2">
                {summary.awaiting_payment.order_count} orders, {summary.awaiting_payment.quantity} units,
                merchandise {money(summary.awaiting_payment.merchandise_total)}, cost {money(summary.awaiting_payment.cost)}.
              </p>
            </section>
          )}

          <section className="card overflow-hidden">
            <div className="px-4 py-3 border-b">
              <h2 className="font-semibold text-gray-900">Latest Transactions</h2>
              <p className="text-xs text-gray-500 mt-1">
                Income and expense entries for the selected dates. Order payments stay on the Income tab in Finance.
              </p>
            </div>
            {transactionsError ? (
              <div className="p-4">
                <LoadError title="Could not load transactions" onRetry={refetchTransactions} />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      {['Type', 'Date', 'Category', 'Description', 'Details', 'Amount'].map((heading) => (
                        <th key={heading} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{heading}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {transactionsLoading ? (
                      <tr><td colSpan="6" className="px-4 py-8 text-center text-gray-500">Loading transactions…</td></tr>
                    ) : transactions.length === 0 ? (
                      <tr><td colSpan="6" className="px-4 py-8 text-center text-gray-500">No manual income or expense entries in this range.</td></tr>
                    ) : transactions.map((row) => (
                      <tr key={row.id}>
                        <td className="px-4 py-3 text-sm">
                          <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                            row.type === 'income' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                          }`}>
                            {row.type === 'income' ? 'Income' : 'Expense'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">{row.date}</td>
                        <td className="px-4 py-3 text-sm">{row.category_label}</td>
                        <td className="px-4 py-3 text-sm max-w-xs truncate">
                          {row.description}
                          {row.reference ? <span className="block text-xs text-gray-400 font-mono">{row.reference}</span> : null}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {row.type === 'income' && row.share_partner_label
                            ? `Share: ${row.share_partner_label}`
                            : row.payee
                              ? `Payee: ${row.payee}`
                              : row.product_name
                                ? `Product: ${row.product_name}`
                                : '—'}
                        </td>
                        <td className={`px-4 py-3 text-sm font-semibold ${row.type === 'income' ? 'text-green-700' : 'text-red-700'}`}>
                          {row.type === 'income' ? '+' : '−'}{money(row.amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </AdminLayout>
  );
}

function Summary({ icon: Icon, label, value, tone, hint }) {
  const tones = {
    green: 'bg-green-100 text-green-600',
    red: 'bg-red-100 text-red-600',
    purple: 'bg-purple-100 text-purple-600',
    blue: 'bg-blue-100 text-blue-600',
  };
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {hint ? <p className="text-xs text-gray-500 mt-1">{hint}</p> : null}
        </div>
        <div className={`p-3 rounded-xl ${tones[tone]}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
}
