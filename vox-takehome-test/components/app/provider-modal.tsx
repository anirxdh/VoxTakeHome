'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Provider } from '@/types/provider';
import { cn } from '@/lib/utils';

interface ProviderModalProps {
  providers: Provider[];
  isOpen: boolean;
  onClose: () => void;
}

export function ProviderModal({ providers, isOpen, onClose }: ProviderModalProps) {
  const [currentIndex, setCurrentIndex] = useState(0);

  // Reset to first provider when modal opens or providers change
  useEffect(() => {
    if (isOpen && providers.length > 0) {
      setCurrentIndex(0);
    }
  }, [isOpen, providers]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'ArrowLeft' && currentIndex > 0) {
        setCurrentIndex(currentIndex - 1);
      } else if (e.key === 'ArrowRight' && currentIndex < providers.length - 1) {
        setCurrentIndex(currentIndex + 1);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentIndex, providers.length, onClose]);

  if (!isOpen) return null;

  const currentProvider = providers[currentIndex];
  const hasMultipleProviders = providers.length > 1;

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-100 flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Modal Content */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="relative z-10 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
          >
            <div className="bg-background border-muted rounded-2xl border shadow-2xl">
              {/* Header */}
              <div className="border-muted flex items-center justify-between border-b px-6 py-4">
                <h2 className="text-xl font-semibold">
                  {providers.length === 0
                    ? 'No Results'
                    : `Provider ${currentIndex + 1} of ${providers.length}`}
                </h2>
                <button
                  onClick={onClose}
                  className="text-muted-foreground hover:text-foreground rounded-lg p-2 transition-colors"
                  aria-label="Close modal"
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 20 20"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  >
                    <path d="M15 5L5 15M5 5l10 10" />
                  </svg>
                </button>
              </div>

              {/* Content */}
              <div className="p-6">
                {providers.length === 0 ? (
                  <div className="text-muted-foreground py-12 text-center">
                    <p className="text-lg">No provider results available</p>
                    <p className="mt-2 text-sm">Try searching for providers using the voice assistant</p>
                  </div>
                ) : (
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={currentIndex}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -20 }}
                      transition={{ duration: 0.2 }}
                      className="space-y-6"
                    >
                      {/* Provider Name & Specialty */}
                      <div>
                        <h3 className="text-2xl font-bold">{currentProvider.full_name}</h3>
                        <p className="text-muted-foreground mt-1 text-lg">{currentProvider.specialty}</p>
                      </div>

                      {/* Rating & Status */}
                      <div className="flex flex-wrap gap-3">
                        <div className="bg-muted flex items-center gap-2 rounded-lg px-3 py-1.5">
                          <span className="text-yellow-500">★</span>
                          <span className="font-medium">{currentProvider.rating.toFixed(1)}</span>
                        </div>
                        <div className="bg-muted flex items-center gap-2 rounded-lg px-3 py-1.5">
                          <span className="text-sm">
                            {currentProvider.years_experience} years experience
                          </span>
                        </div>
                        {currentProvider.board_certified && (
                          <div className="bg-muted flex items-center gap-2 rounded-lg px-3 py-1.5">
                            <span className="text-sm">Board Certified</span>
                          </div>
                        )}
                        {currentProvider.accepting_new_patients && (
                          <div className="bg-green-500/10 text-green-600 dark:text-green-400 flex items-center gap-2 rounded-lg px-3 py-1.5">
                            <span className="text-sm">Accepting New Patients</span>
                          </div>
                        )}
                      </div>

                      {/* Contact Information */}
                      <div className="space-y-3">
                        <h4 className="font-semibold">Contact Information</h4>
                        <div className="bg-muted space-y-2 rounded-lg p-4">
                          <div className="flex items-start gap-3">
                            <span className="text-muted-foreground text-sm">Phone:</span>
                            <a
                              href={`tel:${currentProvider.phone}`}
                              className="hover:underline font-medium"
                            >
                              {currentProvider.phone}
                            </a>
                          </div>
                          <div className="flex items-start gap-3">
                            <span className="text-muted-foreground text-sm">Email:</span>
                            <a
                              href={`mailto:${currentProvider.email}`}
                              className="hover:underline font-medium"
                            >
                              {currentProvider.email}
                            </a>
                          </div>
                          <div className="flex items-start gap-3">
                            <span className="text-muted-foreground text-sm">Address:</span>
                            <div className="font-medium">
                              <div>{currentProvider.address.street}</div>
                              <div>
                                {currentProvider.address.city}, {currentProvider.address.state}{' '}
                                {currentProvider.address.zip}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Languages */}
                      {currentProvider.languages.length > 0 && (
                        <div className="space-y-3">
                          <h4 className="font-semibold">Languages</h4>
                          <div className="flex flex-wrap gap-2">
                            {currentProvider.languages.map((lang, idx) => (
                              <span
                                key={idx}
                                className="bg-muted rounded-md px-3 py-1 text-sm"
                              >
                                {lang}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Insurance */}
                      {currentProvider.insurance_accepted.length > 0 && (
                        <div className="space-y-3">
                          <h4 className="font-semibold">Insurance Accepted</h4>
                          <div className="flex flex-wrap gap-2">
                            {currentProvider.insurance_accepted.map((insurance, idx) => (
                              <span
                                key={idx}
                                className="bg-muted rounded-md px-3 py-1 text-sm"
                              >
                                {insurance}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* License */}
                      <div className="text-muted-foreground border-muted border-t pt-4 text-sm">
                        License Number: {currentProvider.license_number}
                      </div>
                    </motion.div>
                  </AnimatePresence>
                )}
              </div>

              {/* Navigation Footer */}
              {hasMultipleProviders && providers.length > 0 && (
                <div className="border-muted flex items-center justify-between border-t px-6 py-4">
                  <button
                    onClick={() => setCurrentIndex(currentIndex - 1)}
                    disabled={currentIndex === 0}
                    className={cn(
                      'flex items-center gap-2 rounded-lg px-4 py-2 font-medium transition-colors',
                      currentIndex === 0
                        ? 'text-muted-foreground cursor-not-allowed opacity-50'
                        : 'hover:bg-muted'
                    )}
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 16 16"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    >
                      <path d="M10 12L6 8l4-4" />
                    </svg>
                    Previous
                  </button>

                  <div className="text-muted-foreground flex gap-1.5">
                    {providers.map((_, idx) => (
                      <button
                        key={idx}
                        onClick={() => setCurrentIndex(idx)}
                        className={cn(
                          'h-2 w-2 rounded-full transition-all',
                          idx === currentIndex
                            ? 'bg-foreground w-6'
                            : 'bg-muted-foreground/30 hover:bg-muted-foreground/50'
                        )}
                        aria-label={`Go to provider ${idx + 1}`}
                      />
                    ))}
                  </div>

                  <button
                    onClick={() => setCurrentIndex(currentIndex + 1)}
                    disabled={currentIndex === providers.length - 1}
                    className={cn(
                      'flex items-center gap-2 rounded-lg px-4 py-2 font-medium transition-colors',
                      currentIndex === providers.length - 1
                        ? 'text-muted-foreground cursor-not-allowed opacity-50'
                        : 'hover:bg-muted'
                    )}
                  >
                    Next
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 16 16"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    >
                      <path d="M6 12l4-4-4-4" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

