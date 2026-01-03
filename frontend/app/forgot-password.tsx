import React, { useState } from 'react';
import {
    View,
    Text,
    TextInput,
    TouchableOpacity,
    StyleSheet,
    Alert,
    ActivityIndicator,
    KeyboardAvoidingView,
    Platform,
    ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors } from '@/constants/theme';
import { Ionicons } from '@expo/vector-icons';
import { forgotPassword } from '@/services/api';

export default function ForgotPasswordScreen() {
    const [email, setEmail] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isSuccess, setIsSuccess] = useState(false);
    const router = useRouter();
    const colorScheme = useColorScheme();
    const colors = Colors[colorScheme ?? 'light'];

    const validateEmail = (email: string): boolean => {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
    };

    const handleSubmit = async () => {
        if (!email.trim()) {
            Alert.alert('Error', 'Please enter your email address');
            return;
        }

        if (!validateEmail(email)) {
            Alert.alert('Error', 'Please enter a valid email address');
            return;
        }

        setIsLoading(true);
        try {
            await forgotPassword({ email: email.trim() });
            setIsSuccess(true);
        } catch (error: any) {
            Alert.alert('Error', error.message || 'Failed to send reset email');
        } finally {
            setIsLoading(false);
        }
    };

    if (isSuccess) {
        return (
            <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top', 'bottom']}>
                <View style={styles.content}>
                    {/* Success Icon */}
                    <View style={styles.logoSection}>
                        <View style={[styles.logoContainer, { backgroundColor: colors.tint }]}>
                            <Ionicons name="mail-open" size={48} color="#fff" />
                        </View>
                        <Text style={[styles.appName, { color: colors.text }]}>Check Your Email</Text>
                        <Text style={[styles.tagline, { color: colors.icon }]}>
                            If an account with that email exists, we've sent password reset instructions.
                        </Text>
                    </View>

                    {/* Action Card */}
                    <View style={[styles.formCard, { backgroundColor: colorScheme === 'dark' ? '#1a1a1a' : '#fff', borderColor: colors.icon + '30' }]}>
                        <TouchableOpacity
                            style={styles.button}
                            onPress={() => router.push('/reset-password')}
                        >
                            <Text style={styles.buttonText}>Enter Reset Code</Text>
                            <Ionicons name="arrow-forward" size={20} color="#fff" style={styles.buttonIcon} />
                        </TouchableOpacity>

                        <TouchableOpacity
                            style={[styles.secondaryButton, { borderColor: colors.icon + '50' }]}
                            onPress={() => router.replace('/login')}
                        >
                            <Ionicons name="arrow-back" size={20} color={colors.text} style={styles.secondaryButtonIcon} />
                            <Text style={[styles.secondaryButtonText, { color: colors.text }]}>
                                Back to Sign In
                            </Text>
                        </TouchableOpacity>
                    </View>
                </View>
            </SafeAreaView>
        );
    }

    return (
        <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top', 'bottom']}>
            <KeyboardAvoidingView
                style={styles.keyboardView}
                behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            >
                <ScrollView
                    contentContainerStyle={styles.scrollContent}
                    keyboardShouldPersistTaps="handled"
                    showsVerticalScrollIndicator={false}
                >
                    <View style={styles.content}>
                        {/* Logo Section */}
                        <View style={styles.logoSection}>
                            <View style={[styles.logoContainer, { backgroundColor: colors.tint }]}>
                                <Ionicons name="key" size={48} color="#fff" />
                            </View>
                            <Text style={[styles.appName, { color: colors.text }]}>Forgot Password?</Text>
                            <Text style={[styles.tagline, { color: colors.icon }]}>
                                No worries! Enter your email and we'll send you a reset code.
                            </Text>
                        </View>

                        {/* Form Card */}
                        <View style={[styles.formCard, { backgroundColor: colorScheme === 'dark' ? '#1a1a1a' : '#fff', borderColor: colors.icon + '30' }]}>
                            <View style={styles.inputContainer}>
                                <View style={[styles.inputWrapper, { backgroundColor: colorScheme === 'dark' ? '#252525' : '#f5f5f5', borderColor: colors.icon + '30' }]}>
                                    <Ionicons name="mail-outline" size={20} color={colors.icon} style={styles.inputIcon} />
                                    <TextInput
                                        style={[styles.input, { color: colors.text }]}
                                        placeholder="Enter your email"
                                        placeholderTextColor={colors.icon}
                                        value={email}
                                        onChangeText={setEmail}
                                        autoCapitalize="none"
                                        autoCorrect={false}
                                        keyboardType="email-address"
                                        editable={!isLoading}
                                    />
                                </View>
                            </View>

                            <TouchableOpacity
                                style={[styles.button, isLoading && styles.buttonDisabled]}
                                onPress={handleSubmit}
                                disabled={isLoading}
                            >
                                {isLoading ? (
                                    <ActivityIndicator color="#fff" />
                                ) : (
                                    <>
                                        <Text style={styles.buttonText}>Send Reset Code</Text>
                                        <Ionicons name="send" size={20} color="#fff" style={styles.buttonIcon} />
                                    </>
                                )}
                            </TouchableOpacity>
                        </View>

                        {/* Footer */}
                        <View style={styles.footer}>
                            <Text style={[styles.footerText, { color: colors.icon }]}>
                                Remember your password?{' '}
                            </Text>
                            <TouchableOpacity
                                onPress={() => router.push('/login')}
                                disabled={isLoading}
                            >
                                <Text style={[styles.link, { color: colors.tint }]}>Sign In</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                </ScrollView>
            </KeyboardAvoidingView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    keyboardView: {
        flex: 1,
    },
    scrollContent: {
        flexGrow: 1,
    },
    content: {
        flex: 1,
        justifyContent: 'center',
        padding: 24,
    },
    logoSection: {
        alignItems: 'center',
        marginBottom: 32,
    },
    logoContainer: {
        width: 100,
        height: 100,
        borderRadius: 28,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 16,
    },
    appName: {
        fontSize: 28,
        fontWeight: 'bold',
        marginBottom: 8,
        textAlign: 'center',
    },
    tagline: {
        fontSize: 15,
        textAlign: 'center',
        lineHeight: 22,
        paddingHorizontal: 16,
    },
    formCard: {
        borderRadius: 16,
        padding: 24,
        borderWidth: 1,
        marginBottom: 24,
    },
    inputContainer: {
        marginBottom: 20,
    },
    inputWrapper: {
        flexDirection: 'row',
        alignItems: 'center',
        height: 56,
        borderWidth: 1,
        borderRadius: 12,
        paddingHorizontal: 16,
    },
    inputIcon: {
        marginRight: 12,
    },
    input: {
        flex: 1,
        fontSize: 16,
        height: '100%',
    },
    button: {
        backgroundColor: '#10b981',
        height: 56,
        borderRadius: 12,
        flexDirection: 'row',
        justifyContent: 'center',
        alignItems: 'center',
    },
    buttonDisabled: {
        opacity: 0.6,
    },
    buttonText: {
        color: '#fff',
        fontSize: 18,
        fontWeight: '600',
    },
    buttonIcon: {
        marginLeft: 8,
    },
    secondaryButton: {
        height: 56,
        borderRadius: 12,
        flexDirection: 'row',
        justifyContent: 'center',
        alignItems: 'center',
        marginTop: 12,
        borderWidth: 1,
    },
    secondaryButtonIcon: {
        marginRight: 8,
    },
    secondaryButtonText: {
        fontSize: 16,
        fontWeight: '600',
    },
    footer: {
        flexDirection: 'row',
        justifyContent: 'center',
    },
    footerText: {
        fontSize: 15,
    },
    link: {
        fontSize: 15,
        fontWeight: '600',
    },
});
