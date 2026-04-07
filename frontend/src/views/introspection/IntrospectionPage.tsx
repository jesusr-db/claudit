import { useState } from "react";
import {
  Box,
  Heading,
  VStack,
  HStack,
  Select,
  Button,
  Spinner,
  Text,
  Badge,
} from "@chakra-ui/react";
import { useSessions, useIntrospectionAnalyze } from "@/shared/hooks/useApi";
import { InsightCardFeed } from "./components/InsightCardFeed";
import type { IntrospectionResult } from "@/types/api";

const CROSS_SESSION_OPTIONS = [
  { label: "7 days", value: 7 },
  { label: "30 days", value: 30 },
  { label: "90 days", value: 90 },
];

export default function IntrospectionPage() {
  const [selectedSession, setSelectedSession] = useState<string>("");
  const [crossSessionDays, setCrossSessionDays] = useState(30);
  const [cachedResult, setCachedResult] = useState<IntrospectionResult | null>(
    null
  );

  const { data: sessionsData, isLoading: sessionsLoading } = useSessions(
    50,
    0,
    30
  );
  const mutation = useIntrospectionAnalyze();

  const sessions = sessionsData?.sessions || [];

  const handleAnalyze = () => {
    if (!selectedSession) return;
    mutation.mutate(
      { session_id: selectedSession, cross_session_days: crossSessionDays },
      {
        onSuccess: (data) => {
          setCachedResult(data);
        },
      }
    );
  };

  const result = cachedResult;

  return (
    <Box p={8} maxW="960px" mx="auto">
      <VStack align="stretch" spacing={6}>
        {/* Header */}
        <Box>
          <Heading size="lg" mb={1}>
            Introspection
          </Heading>
          <Text fontSize="sm" color="gray.500">
            Analyze session logs to surface recurring failure patterns, root
            causes, and best practices.
          </Text>
        </Box>

        {/* Controls */}
        <Box
          bg="surface.card"
          borderRadius="soft-lg"
          boxShadow="soft"
          border="1px solid"
          borderColor="soft.border"
          p={5}
        >
          <VStack spacing={4} align="stretch">
            <HStack spacing={4} flexWrap="wrap">
              {/* Session selector */}
              <Box flex={2} minW="250px">
                <Text fontSize="xs" fontWeight="600" color="gray.500" mb={1}>
                  Session
                </Text>
                <Select
                  placeholder={
                    sessionsLoading ? "Loading sessions..." : "Select a session"
                  }
                  value={selectedSession}
                  onChange={(e) => {
                    setSelectedSession(e.target.value);
                    setCachedResult(null);
                  }}
                  size="sm"
                  isDisabled={sessionsLoading}
                >
                  {sessions.map((s) => (
                    <option key={s.session_id} value={s.session_id}>
                      {s.session_id.slice(0, 12)}... — {s.event_count} events
                      {s.first_prompt
                        ? ` — ${s.first_prompt.slice(0, 40)}`
                        : ""}
                    </option>
                  ))}
                </Select>
              </Box>

              {/* Cross-session window */}
              <Box minW="140px">
                <Text fontSize="xs" fontWeight="600" color="gray.500" mb={1}>
                  Cross-session window
                </Text>
                <Select
                  value={crossSessionDays}
                  onChange={(e) =>
                    setCrossSessionDays(Number(e.target.value))
                  }
                  size="sm"
                >
                  {CROSS_SESSION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </Select>
              </Box>

              {/* Analyze button */}
              <Box alignSelf="flex-end">
                <Button
                  colorScheme="blue"
                  size="sm"
                  onClick={handleAnalyze}
                  isDisabled={!selectedSession || mutation.isPending}
                  isLoading={mutation.isPending}
                  loadingText="Analyzing..."
                >
                  Analyze Session
                </Button>
              </Box>
            </HStack>

            {/* Re-analyze button (shown after first result) */}
            {result && !mutation.isPending && (
              <HStack spacing={2}>
                <Badge variant="subtle" colorScheme="green" fontSize="xs">
                  {result.cards.length} pattern
                  {result.cards.length !== 1 ? "s" : ""} found
                </Badge>
                <Button
                  size="xs"
                  variant="ghost"
                  colorScheme="gray"
                  onClick={handleAnalyze}
                >
                  Re-analyze
                </Button>
              </HStack>
            )}
          </VStack>
        </Box>

        {/* Loading state */}
        {mutation.isPending && (
          <Box textAlign="center" py={8}>
            <Spinner size="lg" color="brand.500" mb={3} />
            <Text fontSize="sm" color="gray.500">
              Analyzing session patterns... this may take up to 60 seconds.
            </Text>
          </Box>
        )}

        {/* Mutation error (network/HTTP) */}
        {mutation.isError && !result && (
          <Box
            bg="red.50"
            border="1px solid"
            borderColor="red.200"
            borderRadius="md"
            p={4}
          >
            <Text color="red.600" fontSize="sm">
              {mutation.error?.message || "An error occurred"}
            </Text>
          </Box>
        )}

        {/* Results */}
        {result && !mutation.isPending && (
          <InsightCardFeed
            cards={result.cards}
            analysisError={result.analysis_error}
            onRetry={handleAnalyze}
          />
        )}
      </VStack>
    </Box>
  );
}
