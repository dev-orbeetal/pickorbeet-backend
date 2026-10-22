import { useState, useEffect } from 'react';
import {
  DollarSign, TrendingUp, TrendingDown, Wallet,
  Calendar, Download, Plus, ArrowUpRight, ArrowDownRight,
  PiggyBank, CreditCard, Banknote, Receipt
} from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { useGetDashboardStatsQuery } from '@/store/api/dashboardApi';
import { useGetOrdersQuery } from '@/store/api/ordersApi';

export default function MoneyManagementPage() {
  const [dateRange, setDateRange] = useState({
    start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
  });
  const [showAddModal, setShowAddModal] = useState(false);
  const [expenses, setExpenses] = useState([]);
  const [newExpense, setNewExpense] = useState({
    type: 'expense',
    category: '',
    amount: '',
    description: '',
    date: new Date().toISOString().split('T')[0],
  });

  const { data: dashboardData, isLoading: dashboardLoading } = useGetDashboardStatsQuery();
  const { data: ordersData } = useGetOrdersQuery({
    order_status: 'delivered',
    payment_status: 'paid'
  });

  // Calculate financial metrics
  const totalRevenue = dashboardData?.total_revenue || 0;
  const totalOrders = dashboardData?.total_orders || 0;
  const deliveredOrders = ordersData?.results?.filter(o => o.order_status === 'delivered') || [];
  const paidRevenue = deliveredOrders.reduce((sum, o) => sum + parseFloat(o.total || 0), 0);

  const totalExpenses = expenses.reduce((sum, e) => e.type === 'expense' ? sum + parseFloat(e.amount) : sum, 0);
  const totalIncome = expenses.reduce((sum, e) => e.type === 'income' ? sum + parseFloat(e.amount) : sum, 0);
  const netProfit = paidRevenue + totalIncome - totalExpenses;

  const expenseCategories = [
    'Inventory Purchase',
    'Shipping & Delivery',
    'Marketing & Ads',
    'Utilities',
    'Rent',
    'Salaries',
    'Packaging',
    'Software & Tools',
    'Miscellaneous',
  ];

  const incomeCategories = [
    'Product Sales',
    'Refund Received',
    'Investment',
    'Other Income',
  ];

  const handleAddExpense = () => {
    if (!newExpense.category || !newExpense.amount) {
      toast.error('Please fill in all required fields');
      return;
    }

    const expense = {
      id: Date.now(),
      ...newExpense,
      amount: parseFloat(newExpense.amount),
      createdAt: new Date().toISOString(),
    };

    setExpenses([expense, ...expenses]);
    setNewExpense({
      type: 'expense',
      category: '',
      amount: '',
      description: '',
      date: new Date().toISOString().split('T')[0],
    });
    setShowAddModal(false);
    toast.success(`${newExpense.type === 'expense' ? 'Expense' : 'Income'} added successfully`);
  };

  const downloadFinancialReport = () => {
    let csvContent = 'Financial Report\n';
    csvContent += `Date Range,${dateRange.start_date} to ${dateRange.end_date}\n\n`;
    csvContent += 'Summary\n';
    csvContent += `Total Revenue (Orders),${paidRevenue}\n`;
    csvContent += `Additional Income,${totalIncome}\n`;
    csvContent += `Total Expenses,${totalExpenses}\n`;
    csvContent += `Net Profit,${netProfit}\n\n`;

    csvContent += 'Transactions\n';
    csvContent += 'Date,Type,Category,Amount,Description\n';
    expenses.forEach(e => {
      csvContent += `${e.date},${e.type},${e.category},${e.amount},"${e.description || ''}"\n`;
    });

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `financial_report_${dateRange.start_date}_to_${dateRange.end_date}.csv`;
    link.click();
  };

  return (
    <AdminLayout title="Money Management">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Money Management</h1>
          <p className="text-gray-500">Track your income, expenses, and profit</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowAddModal(true)}
            className="btn btn-primary"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Transaction
          </button>
          <button
            onClick={downloadFinancialReport}
            className="btn btn-secondary"
          >
            <Download className="w-4 h-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      {/* Date Range Filter */}
      <div className="card p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <Calendar className="w-5 h-5 text-gray-400" />
          <input
            type="date"
            value={dateRange.start_date}
            onChange={(e) => setDateRange({ ...dateRange, start_date: e.target.value })}
            className="input w-auto"
          />
          <span className="text-gray-500">to</span>
          <input
            type="date"
            value={dateRange.end_date}
            onChange={(e) => setDateRange({ ...dateRange, end_date: e.target.value })}
            className="input w-auto"
          />
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 mb-1">Total Revenue</p>
              <p className="text-2xl font-bold text-gray-900">৳{paidRevenue.toLocaleString()}</p>
              <p className="text-xs text-gray-400 mt-1">From {deliveredOrders.length} orders</p>
            </div>
            <div className="p-3 bg-green-100 rounded-xl">
              <DollarSign className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 mb-1">Additional Income</p>
              <p className="text-2xl font-bold text-blue-600">৳{totalIncome.toLocaleString()}</p>
              <p className="text-xs text-gray-400 mt-1">Other income sources</p>
            </div>
            <div className="p-3 bg-blue-100 rounded-xl">
              <ArrowUpRight className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 mb-1">Total Expenses</p>
              <p className="text-2xl font-bold text-red-600">৳{totalExpenses.toLocaleString()}</p>
              <p className="text-xs text-gray-400 mt-1">{expenses.filter(e => e.type === 'expense').length} transactions</p>
            </div>
            <div className="p-3 bg-red-100 rounded-xl">
              <ArrowDownRight className="w-6 h-6 text-red-600" />
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 mb-1">Net Profit</p>
              <p className={`text-2xl font-bold ${netProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ৳{netProfit.toLocaleString()}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {netProfit >= 0 ? 'Profit' : 'Loss'}
              </p>
            </div>
            <div className={`p-3 rounded-xl ${netProfit >= 0 ? 'bg-green-100' : 'bg-red-100'}`}>
              <PiggyBank className={`w-6 h-6 ${netProfit >= 0 ? 'text-green-600' : 'text-red-600'}`} />
            </div>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        {/* Expense Breakdown */}
        <div className="card p-6">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Receipt className="w-5 h-5 text-red-500" />
            Expense Breakdown
          </h3>
          {expenses.filter(e => e.type === 'expense').length === 0 ? (
            <p className="text-gray-500 text-center py-8">No expenses recorded yet</p>
          ) : (
            <div className="space-y-3">
              {expenseCategories.map(category => {
                const categoryTotal = expenses
                  .filter(e => e.type === 'expense' && e.category === category)
                  .reduce((sum, e) => sum + e.amount, 0);
                if (categoryTotal === 0) return null;
                const percentage = totalExpenses > 0 ? (categoryTotal / totalExpenses * 100).toFixed(1) : 0;
                return (
                  <div key={category}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-600">{category}</span>
                      <span className="font-medium">৳{categoryTotal.toLocaleString()}</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-2">
                      <div
                        className="bg-red-500 h-2 rounded-full"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Income Breakdown */}
        <div className="card p-6">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Banknote className="w-5 h-5 text-green-500" />
            Income Sources
          </h3>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Product Sales</span>
                <span className="font-medium">৳{paidRevenue.toLocaleString()}</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2">
                <div
                  className="bg-green-500 h-2 rounded-full"
                  style={{ width: `${(paidRevenue / (paidRevenue + totalIncome) * 100) || 0}%` }}
                />
              </div>
            </div>
            {incomeCategories.slice(1).map(category => {
              const categoryTotal = expenses
                .filter(e => e.type === 'income' && e.category === category)
                .reduce((sum, e) => sum + e.amount, 0);
              if (categoryTotal === 0) return null;
              return (
                <div key={category}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">{category}</span>
                    <span className="font-medium">৳{categoryTotal.toLocaleString()}</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full"
                      style={{ width: `${(categoryTotal / (paidRevenue + totalIncome) * 100) || 0}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="card overflow-hidden">
        <div className="p-4 border-b bg-gray-50 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Recent Transactions</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left py-3 px-4 table-header">Date</th>
                <th className="text-left py-3 px-4 table-header">Type</th>
                <th className="text-left py-3 px-4 table-header">Category</th>
                <th className="text-left py-3 px-4 table-header">Description</th>
                <th className="text-right py-3 px-4 table-header">Amount</th>
              </tr>
            </thead>
            <tbody>
              {expenses.length === 0 ? (
                <tr>
                  <td colSpan="5" className="text-center py-8 text-gray-500">
                    No transactions recorded. Click "Add Transaction" to get started.
                  </td>
                </tr>
              ) : (
                expenses.map((expense) => (
                  <tr key={expense.id} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-4 text-gray-600">
                      {new Date(expense.date).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`badge ${expense.type === 'income' ? 'badge-success' : 'badge-danger'}`}>
                        {expense.type}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-medium">{expense.category}</td>
                    <td className="py-3 px-4 text-gray-600">{expense.description || '-'}</td>
                    <td className={`py-3 px-4 text-right font-semibold ${expense.type === 'income' ? 'text-green-600' : 'text-red-600'}`}>
                      {expense.type === 'income' ? '+' : '-'}৳{expense.amount.toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Transaction Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-md p-6">
            <h2 className="text-xl font-semibold mb-4">Add Transaction</h2>

            <div className="space-y-4">
              {/* Type Selection */}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setNewExpense({ ...newExpense, type: 'expense', category: '' })}
                  className={`flex-1 py-2 px-4 rounded-lg border-2 transition-colors ${newExpense.type === 'expense'
                      ? 'border-red-500 bg-red-50 text-red-700'
                      : 'border-gray-200 hover:border-gray-300'
                    }`}
                >
                  <ArrowDownRight className="w-4 h-4 inline mr-2" />
                  Expense
                </button>
                <button
                  type="button"
                  onClick={() => setNewExpense({ ...newExpense, type: 'income', category: '' })}
                  className={`flex-1 py-2 px-4 rounded-lg border-2 transition-colors ${newExpense.type === 'income'
                      ? 'border-green-500 bg-green-50 text-green-700'
                      : 'border-gray-200 hover:border-gray-300'
                    }`}
                >
                  <ArrowUpRight className="w-4 h-4 inline mr-2" />
                  Income
                </button>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category *</label>
                <select
                  value={newExpense.category}
                  onChange={(e) => setNewExpense({ ...newExpense, category: e.target.value })}
                  className="input"
                >
                  <option value="">Select category</option>
                  {(newExpense.type === 'expense' ? expenseCategories : incomeCategories).map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Amount (৳) *</label>
                <input
                  type="number"
                  value={newExpense.amount}
                  onChange={(e) => setNewExpense({ ...newExpense, amount: e.target.value })}
                  className="input"
                  placeholder="0.00"
                  min="0"
                  step="0.01"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Date</label>
                <input
                  type="date"
                  value={newExpense.date}
                  onChange={(e) => setNewExpense({ ...newExpense, date: e.target.value })}
                  className="input"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={newExpense.description}
                  onChange={(e) => setNewExpense({ ...newExpense, description: e.target.value })}
                  className="input"
                  rows={2}
                  placeholder="Optional description..."
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowAddModal(false)}
                className="btn btn-secondary flex-1"
              >
                Cancel
              </button>
              <button
                onClick={handleAddExpense}
                className="btn btn-primary flex-1"
              >
                Add Transaction
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
